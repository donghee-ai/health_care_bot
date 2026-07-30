#!/usr/bin/env python3
"""헬스케어 봇 통합 진입점 - 1 process, 1 컨테이너.

흐름:
  카메라 → MoveNet Thunder INT8 → 17 keypoint
      ├─ 각도 계산 (knee / elbow)
      ├─ rep counter (mode에 따라 squat / pushup, auto는 자세 자동 분류)
      ├─ PTZ controller (추적점: 스쿼트는 무릎 가중 중심, 그 외 상반신 중심 → 프레임-아웃 → Arduino 시리얼 명령)
      └─ HTTP serve (MJPEG + stats.json)
"""
import argparse
import os
import sys
import threading
import time
from collections import deque
from pathlib import Path

import numpy as np
import cv2

# 같은 폴더 모듈
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pose_utils import KP, letterbox_square, unletterbox_kp, person_center_normalized, person_center_weighted, draw_pose
from angles import knee_angle, shoulder_elev_angle, pick_angle, body_orientation
from exercise_counter import SquatCounter, OverheadPressCounter, LateralRaiseCounter
from ptz_controller import PTZController
from http_server import update_live_state, start_server, init_app, viewer_count
import app_state

try:
    from ai_edge_litert import interpreter as tflite
    RUNTIME = "ai_edge_litert"
except ImportError:
    try:
        import tflite_runtime.interpreter as tflite
        RUNTIME = "tflite_runtime"
    except ImportError:
        import tensorflow.lite as tflite
        RUNTIME = "tensorflow.lite"


# === 자세별 좌/우 keypoint 강조 인덱스 (draw용) ===
_HIGHLIGHT_SQUAT = [KP["left_knee"], KP["right_knee"]]
_HIGHLIGHT_ARM = [KP["left_elbow"], KP["right_elbow"], KP["left_wrist"], KP["right_wrist"]]


def get_rss_mb():
    try:
        with open('/proc/self/status') as f:
            for line in f:
                if line.startswith('VmRSS:'):
                    return int(line.split()[1]) / 1024.0
    except Exception:
        return None
    return None


def get_cpu_temp_c():
    """SoC 온도 (millidegree C → C). Windows/온도 노드 없는 환경에서는 None."""
    try:
        with open('/sys/class/thermal/thermal_zone0/temp') as f:
            return int(f.read().strip()) / 1000.0
    except Exception:
        return None


_prev_cpu_sample = None


def get_cpu_percent():
    """시스템 전체 CPU 사용률 0~100 (전 코어 합산을 100%로 정규화).

    /proc/stat은 부팅 이후 누적 시간이라 값 하나로는 사용률을 알 수 없다.
    직전 호출과의 차분으로 구간 사용률을 낸다 → **첫 호출은 항상 None**.
    (컨테이너 안에서도 /proc/stat은 호스트 전체 값을 보여주므로 디바이스
    전체 부하가 잡힌다. 이 프로세스만의 사용률이 아니다.)
    """
    global _prev_cpu_sample
    try:
        with open('/proc/stat') as f:
            parts = f.readline().split()
        if not parts or parts[0] != 'cpu':
            return None
        vals = [int(v) for v in parts[1:]]
    except Exception:
        return None
    if len(vals) < 4:
        return None
    idle = vals[3] + (vals[4] if len(vals) > 4 else 0)   # idle + iowait
    total = sum(vals)
    prev, _prev_cpu_sample = _prev_cpu_sample, (total, idle)
    if prev is None:
        return None
    d_total, d_idle = total - prev[0], idle - prev[1]
    if d_total <= 0:
        return None
    return max(0.0, min(100.0, (d_total - d_idle) / d_total * 100.0))


class FrameGrabber:
    """카메라를 별도 스레드에서 계속 읽어 항상 최신 프레임 1장만 보관.

    함정 방지: 추론 루프가 카메라 캡처 속도보다 느리면(예: 33ms/frame 캡처 vs
    90ms/frame 추론) `cap.read()`를 메인 루프에서 직접 부를 경우 드라이버
    버퍼에 안 읽힌 프레임이 쌓여 지연이 계속 누적된다 -
    `cv2.CAP_PROP_BUFFERSIZE`는 V4L2/UVC 드라이버에 따라 무시되는 경우가
    흔해 안전장치가 못 됨. 큐 대신 "최신 프레임 1장 덮어쓰기" 방식으로
    이 누적을 원천 차단한다.
    """

    def __init__(self, cap):
        self._cap = cap
        self._lock = threading.Lock()
        self._frame = None
        self._frame_id = 0
        self._dropped = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()
        return self

    def _run(self):
        while not self._stop.is_set():
            ret, frame = self._cap.read()
            if not ret or frame is None:
                self._dropped += 1
                time.sleep(0.01)
                continue
            with self._lock:
                self._frame = frame
                self._frame_id += 1

    def latest(self):
        """(frame_id, frame) - frame_id로 새 프레임 여부 판단."""
        with self._lock:
            return self._frame_id, self._frame

    @property
    def dropped(self):
        return self._dropped

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=1.0)


def parse_args():
    ap = argparse.ArgumentParser(description="UNO Q Health Care Bot")
    ap.add_argument("model", help="MoveNet Thunder INT8 TFLite 경로")
    ap.add_argument("--mode", choices=["squat", "overhead", "lateral"], default="squat",
                    help="운동 종목 (웹 UI에서 /api/mode로 실시간 변경). 정면 선택식 - 자동분류 없음")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--conf", type=float, default=0.3,
                    help="keypoint confidence 임계")
    ap.add_argument("--side", choices=["left", "right", "avg", "better"], default="better",
                    help="카운터 입력 각도 좌/우 선택 (기본 better)")
    ap.add_argument("--max-frames", type=int, default=0)
    ap.add_argument("--print-every", type=int, default=15)

    # 임계 (squat/pushup별 default가 다르지만 같은 플래그로 노출)
    ap.add_argument("--squat-down-th", type=float, default=100.0)
    ap.add_argument("--squat-up-th", type=float, default=140.0)
    ap.add_argument("--overhead-down-th", type=float, default=60.0)
    ap.add_argument("--overhead-up-th", type=float, default=140.0)
    ap.add_argument("--lateral-down-th", type=float, default=35.0)
    ap.add_argument("--lateral-up-th", type=float, default=80.0)
    ap.add_argument("--min-dwell-ms", type=float, default=200.0)

    # PTZ (ST3215 시리얼 버스 서보 직결 - MCU 경유 아님)
    ap.add_argument("--serial", default="",
                    help="서보 버스 어댑터 포트 (예: /dev/ttyUSB0, COM9). 미지정 시 PTZ 비활성")
    ap.add_argument("--baudrate", type=int, default=1_000_000, help="ST3215 버스 기본 baud")
    ap.add_argument("--frame-out-grace", type=int, default=15, help="미검출 N프레임 후 LOST")
    ap.add_argument("--ptz-cooldown-ms", type=float, default=250.0)
    ap.add_argument("--sector-side", type=float, default=1.0 / 6.0,
                    help="좌우 섹터 폭 (기본 1/6 → 무릎을 중앙 4/6 밴드에 유지)")
    ap.add_argument("--pitch-deadzone", type=float, default=0.20,
                    help="pitch 데드존 - 넓게 잡아 스쿼트 상하 동작을 무시")
    ap.add_argument("--pitch-target-y", type=float, default=0.62,
                    help="pitch 세로 기준점 (무릎이 화면 하단 1/3쯤 오도록)")
    ap.add_argument("--lock-frames", type=int, default=10,
                    help="존 안에 N프레임 머물면 잠금(정지). 0=잠금 끄기")
    ap.add_argument("--track-scale", type=float, default=0.5, help="추적 속도 배율")
    ap.add_argument("--both-knee-scale", type=float, default=0.5,
                    help="양 무릎 보일 때 추가 속도 배율")
    ap.add_argument("--yaw-sign", type=int, default=1, choices=[-1, 1])
    ap.add_argument("--pitch-sign", type=int, default=1, choices=[-1, 1])

    # HTTP
    ap.add_argument("--serve", type=int, default=0,
                    help="HTTP MJPEG 포트 (0 = 비활성)")
    ap.add_argument("--jpeg-quality", type=int, default=70)
    ap.add_argument("--idle-skip-draw", action="store_true",
                    help="스트림 뷰어가 0명이면 그리기+인코딩을 건너뛴다(연산 집중 모드). "
                         "미지정 시 기존과 동일하게 항상 그린다.")
    return ap.parse_args()


def select_counter(mode: str, squat_c, overhead_c, lateral_c):
    """모드(웹 UI에서 선택)로 카운터를 고른다. 전부 정면 종목이라 자동분류 없음."""
    if mode == "overhead":
        return overhead_c, "overhead"
    if mode == "lateral":
        return lateral_c, "lateral"
    return squat_c, "squat"


def compute_angle(kp, exercise: str, conf_th: float, side: str):
    """선택된 운동에 따라 좌/우 각도 + 대표 각도 반환."""
    if exercise == "squat":
        left = knee_angle(kp, "left", conf_th)
        right = knee_angle(kp, "right", conf_th)
    elif exercise in ("overhead", "lateral"):
        left = shoulder_elev_angle(kp, "left", conf_th)
        right = shoulder_elev_angle(kp, "right", conf_th)
    else:
        return None, None, None
    return left, right, pick_angle(left, right, mode=side)


def main():
    args = parse_args()

    model_path = Path(args.model)
    if not model_path.exists():
        sys.exit(f"ERROR: model not found: {model_path}")

    itp = tflite.Interpreter(model_path=str(model_path), num_threads=args.threads)
    itp.allocate_tensors()
    in_d = itp.get_input_details()[0]
    out_d = itp.get_output_details()[0]
    _, h_in, w_in, _ = (int(x) for x in in_d['shape'])
    assert h_in == w_in, f"expected square input, got {h_in}x{w_in}"

    print(f"== UNO Q Health Care Bot ({RUNTIME}) ==")
    print(f"  model    : {model_path}")
    print(f"  input    : {w_in}x{h_in} {in_d['dtype'].__name__}")
    print(f"  mode     : {args.mode}")
    print(f"  camera   : /dev/video{args.camera} {args.width}x{args.height}")
    print(f"  threads  : {args.threads}, conf {args.conf}, side {args.side}")
    print(f"  squat    : down<{args.squat_down_th}, up>{args.squat_up_th}")
    print(f"  overhead : down<{args.overhead_down_th}, up>{args.overhead_up_th}")
    print(f"  lateral  : down<{args.lateral_down_th}, up>{args.lateral_up_th}")
    print(f"  ptz      : serial={args.serial or '(disabled)'} sector={args.sector_side:.3f} "
          f"lock={args.lock_frames}f grace={args.frame_out_grace}f scale={args.track_scale}")
    if args.serve:
        print(f"  serve    : http://<device-ip>:{args.serve}/ (DEBUG no-auth)")
    print()

    # PTZ
    ptz = PTZController(
        serial_port=args.serial or None,
        baudrate=args.baudrate,
        conf_th=args.conf,
        frame_out_grace=args.frame_out_grace,
        command_cooldown_ms=args.ptz_cooldown_ms,
        sector_side=args.sector_side,
        pitch_deadzone=args.pitch_deadzone,
        pitch_target_y=args.pitch_target_y,
        lock_frames=args.lock_frames,
        track_scale=args.track_scale,
        both_knee_scale=args.both_knee_scale,
        yaw_sign=args.yaw_sign,
        pitch_sign=args.pitch_sign,
    )
    ptz.open()

    # Counters - 세 종목 모두 생성 (웹에서 모드 전환 시 각 상태 유지)
    squat_c = SquatCounter(args.squat_down_th, args.squat_up_th, args.min_dwell_ms)
    overhead_c = OverheadPressCounter(args.overhead_down_th, args.overhead_up_th, args.min_dwell_ms)
    lateral_c = LateralRaiseCounter(args.lateral_down_th, args.lateral_up_th, args.min_dwell_ms)

    _last_fps = {"value": 0.0}
    app_state.set_mode(args.mode)

    # HTTP
    if args.serve:
        init_app(ptz=ptz, squat_c=squat_c, overhead_c=overhead_c, lateral_c=lateral_c,
                 avg_fps_fn=lambda: _last_fps["value"])
        try:
            start_server(args.serve)
            print(f"  [http] started on port {args.serve}\n")
            print(f"  [app]  http://<device-ip>:{args.serve}/app  (viewer)")
            print(f"  [app]  http://<device-ip>:{args.serve}/app?role=operator  (operator)\n")
        except Exception as e:
            sys.exit(f"ERROR: failed to start HTTP server: {e}")

    # Camera
    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        sys.exit(f"ERROR: cannot open camera /dev/video{args.camera}")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"  actual   : {actual_w}x{actual_h}\n")

    grabber = FrameGrabber(cap).start()

    loop_window = deque(maxlen=30)
    frame_idx = 0
    last_frame_id = -1
    last_orient = None
    t_start = time.perf_counter()

    print("[run] start (Ctrl+C to stop)\n")

    try:
        while True:
            frame_id, frame = grabber.latest()
            if frame is None or frame_id == last_frame_id:
                # 아직 새 프레임 없음 - 그리버 스레드가 캡처하는 동안 바쁜 대기 회피
                time.sleep(0.005)
                continue
            last_frame_id = frame_id
            t0 = time.perf_counter()

            padded, pad_info = letterbox_square(frame, target=h_in)
            rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
            x = np.expand_dims(rgb.astype(np.uint8), 0)

            itp.set_tensor(in_d['index'], x)
            itp.invoke()
            raw = itp.get_tensor(out_d['index'])  # [1,1,17,3]

            kp = unletterbox_kp(raw[0, 0], pad_info, target=h_in)

            # 운동 종목 결정 (mode는 /api/mode로 앱에서 실시간 변경 가능) - PTZ 추적점
            # 선택보다 먼저 필요 (스쿼트면 무릎 가중 추적으로 바꿔야 하므로)
            orient = body_orientation(kp, args.conf)
            if orient is not None:
                last_orient = orient
            live_mode = app_state.get_mode() if args.serve else args.mode
            counter, exercise = select_counter(live_mode, squat_c, overhead_c, lateral_c)

            # 통계/오버레이용 사람 중심점 (PTZ 추적점과는 별개)
            if exercise == "squat":
                x_norm, y_norm = person_center_weighted(kp, actual_h, actual_w, args.conf)
            else:
                x_norm, y_norm = person_center_normalized(kp, actual_h, actual_w, args.conf)

            # PTZ 추적 - 종목별 타깃/프레이밍: 스쿼트=하체(무릎), 상체운동=상체(어깨,
            # 머리 위 팔이 안 잘리게). 컨트롤러가 keypoint에서 목표점을 직접 산출.
            ptz.set_track_mode(exercise)
            now_ms = time.perf_counter() * 1000.0
            ptz_cmd = ptz.update(kp, actual_h, actual_w, now_ms)

            left = right = chosen = None
            rep_event = None
            if counter is not None:
                left, right, chosen = compute_angle(kp, exercise, args.conf, args.side)
                rep_event = counter.update(chosen, now_ms=now_ms)

            # === Draw overlay: 스켈레톤(pose)만 ===
            # 수치 텍스트(FPS/각도/REPS/PTZ)는 웹 UI가 stats.json으로 표시하므로
            # 영상에 굽지 않는다 — 중복 제거 + putText 비용 절감. 골격은 유지.
            #
            # --idle-skip-draw(연산 집중 모드): 스트림 뷰어가 0명이면 그리기+
            # 인코딩을 통째로 건너뛴다. 플래그가 없으면(기본) 항상 그려서
            # 기존 동작과 100% 동일하다. stats.json 숫자는 어느 경우든 계속 흐른다.
            want_video = True
            if args.serve and args.idle_skip_draw:
                want_video = viewer_count() > 0
            if want_video:
                annotated = frame.copy()
                highlight = _HIGHLIGHT_ARM if exercise in ("overhead", "lateral") else _HIGHLIGHT_SQUAT
                draw_pose(annotated, kp, conf_th=args.conf, highlight=highlight)
            else:
                annotated = None

            # FPS 계산 (영상 오버레이는 없앴지만 stats.json/로그에 여전히 필요)
            ms_loop = (time.perf_counter() - t0) * 1000.0
            loop_window.append(ms_loop)
            avg_ms = sum(loop_window) / len(loop_window)
            fps = 1000.0 / avg_ms if avg_ms > 0 else 0.0
            _last_fps["value"] = round(fps, 2)

            # PTZ 스냅샷 (stats.json + 아래 print/로그에서 사용)
            ptz_snap = ptz.snapshot()

            frame_idx += 1

            # HTTP 스트림 갱신
            if args.serve:
                live = {
                    "frame": frame_idx,
                    "fps": round(fps, 2),
                    "loop_ms": round(ms_loop, 2),
                    "mode": live_mode,
                    "exercise_active": exercise,
                    "orientation": last_orient,
                    "angle_deg": {
                        "left": round(left, 1) if left is not None else None,
                        "right": round(right, 1) if right is not None else None,
                        "used": round(chosen, 1) if chosen is not None else None,
                    },
                    "person_center_norm": [
                        round(x_norm, 3) if x_norm is not None else None,
                        round(y_norm, 3) if y_norm is not None else None,
                    ],
                    "squat": squat_c.snapshot(),
                    "overhead": overhead_c.snapshot(),
                    "lateral": lateral_c.snapshot(),
                    "ptz": ptz_snap,
                    "last_ptz_cmd": ptz_cmd,
                    "dropped_frames": grabber.dropped,
                    "rss_mb": round(get_rss_mb() or 0.0, 1),
                    "cpu_temp_c": round(cpu_temp_c, 1) if (cpu_temp_c := get_cpu_temp_c()) is not None else None,
                    "cpu_percent": round(cpu_pct, 1) if (cpu_pct := get_cpu_percent()) is not None else None,
                }
                if rep_event:
                    live["last_event"] = {
                        "exercise": exercise,
                        "type": rep_event[0],
                        "rep_total": rep_event[1],
                        "min_angle_deg": round(rep_event[2], 1),
                        "frame": frame_idx,
                    }
                update_live_state(annotated, live, q=args.jpeg_quality, encode=want_video)

            if rep_event:
                print(f"  ★ {exercise.upper()} REP #{rep_event[1]}  "
                      f"bottom={rep_event[2]:.0f}°  (frame {frame_idx})")

            if frame_idx % args.print_every == 0:
                la = f"{left:.0f}" if left is not None else "?"
                ra = f"{right:.0f}" if right is not None else "?"
                ex = exercise or "-"
                reps = counter.reps if counter is not None else 0
                print(f"[{frame_idx:5d}] fps={fps:5.2f}  {ex:>6s} "
                      f"L={la:>3s} R={ra:>3s}°  reps={reps:3d}  "
                      f"ptz={ptz_snap['state']:<8s} cmd={ptz_cmd or '-'}")

            if args.max_frames > 0 and frame_idx >= args.max_frames:
                break

    except KeyboardInterrupt:
        print("\n[stop] interrupted")
    finally:
        grabber.stop()
        try:
            cap.release()
        except Exception:
            pass
        ptz.close()

        elapsed = time.perf_counter() - t_start
        print()
        print("=" * 64)
        print(f"  SUMMARY  frames={frame_idx}  elapsed={elapsed:.1f}s")
        print(f"     fps_effective : {frame_idx / max(elapsed, 1e-9):.2f}")
        print(f"     dropped       : {grabber.dropped}")
        print(f"     squat reps    : {squat_c.reps}")
        print(f"     overhead reps : {overhead_c.reps}")
        print(f"     lateral reps  : {lateral_c.reps}")
        print(f"     ptz cmds      : pan={ptz.n_pan_cmds} tilt={ptz.n_tilt_cmds}")
        print("=" * 64)


if __name__ == "__main__":
    main()
