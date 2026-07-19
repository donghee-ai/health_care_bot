"""로컬 PC 테스트: 카메라 + MoveNet 포즈 + ST3215 PTZ 추적 (버스 직결, MCU 없음).

이 PC에서 웹캠으로 사람을 잡고, 두 무릎 중점을 화면 중앙에 맞추도록
yaw(ID=1)/pitch(ID=2) 서보를 st3215_bus.py로 직접 구동한다 (COM 포트).

추적 방식 (도리도리 방지):
  - 목표점 = 두 무릎 중점(기본). 안 보이면 어깨/엉덩이 가중 중심으로 폴백.
  - EMA 스무딩으로 키포인트 지터 완화.
  - 획득→잠금: 목표가 중앙 데드존에 N프레임 연속 머무르면 '잠금(정지)'.
    사람이 크게 벗어날 때(재개 임계)만 다시 추적. → 미세 흔들림 제거.

안전: 기본은 dry-run(서보 안 움직임, 계산/표시만). --drive를 줘야 실제로 서보가 돈다.
소프트리밋(yaw 90~270, pitch 150~210 = 중앙 180 기준 ±90/±30, tick 2047 캘리브레이션)은
항상 클램프. 속도는 안전속도(569 tick/s).

사용법:
  # 카메라+포즈만 (창, q로 종료)
  python scripts/ptz_camera_track.py --port COM9 --camera 1
  # 서보 구동
  python scripts/ptz_camera_track.py --port COM9 --camera 1 --drive
  # 한 축씩 방향 시험
  python scripts/ptz_camera_track.py --port COM9 --camera 1 --drive --axis yaw
  # 방향 반대면 부호 뒤집기
  python scripts/ptz_camera_track.py --port COM9 --camera 1 --drive --yaw-sign -1
  # 잠금 끄고 계속 추적하고 싶으면
  python scripts/ptz_camera_track.py --port COM9 --camera 1 --drive --lock-frames 0
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))                    # scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))     # src/

import cv2
import numpy as np

from ai_edge_litert import interpreter as tflite
from pose_utils import (
    KP, letterbox_square, unletterbox_kp,
    person_center_normalized, person_center_weighted, draw_pose,
)
from angles import knee_angle, pick_angle
from exercise_counter import SquatCounter
import st3215_bus as bus

# 서보 각도 컨벤션 (이 스크립트 절대각 = tick / TICKS_PER_DEG, 캘리브레이션 중앙 tick2047 ≈ 180°)
YAW_ID = 1
PITCH_ID = 2
YAW_CENTER = 180.0
YAW_MIN, YAW_MAX = 90.0, 270.0      # 중앙 ±90° (실측)
PITCH_CENTER = 180.0
PITCH_MIN, PITCH_MAX = 150.0, 210.0  # 중앙 ±30° (실측)

DEADZONE = 0.10          # 화면 중앙에서 이만큼 안쪽이면 정지 (지터 방지)
REENGAGE = 0.18          # 잠금 상태에서 이 이상 벗어나면 다시 추적 (히스테리시스)
LOCK_FRAMES = 10         # 중앙에 이만큼 연속 프레임 머무르면 잠금(정지) — 도리도리 방지
SMOOTH_ALPHA = 0.4       # 목표점 EMA 계수 (작을수록 부드럽지만 느림)
GAIN = 8.0               # error(0~0.5) → 스텝 각도
MAX_STEP = 4.0           # 한 명령당 최대 각도 변화
TRACK_SCALE = 0.5        # 추적 속도 배율 (현재의 1/2)
BOTH_KNEE_SCALE = 0.5    # 양 무릎 다 보이면 추가로 1/2 (총 1/4, 더 천천히)
SECTOR_SIDE = 1.0 / 6.0  # 좌우 섹터 각 1/6, 중앙 4/6 밴드에 무릎을 유지
YAW_REENGAGE_HYST = 0.05 # yaw 잠금 해제 히스테리시스 여유
COOLDOWN_MS = 250.0      # 명령 사이 최소 간격 (서보 소화 시간)
SPEED = 569              # 안전속도 (20ms/° 등가)
ACC = 20

_HL_KNEE = [KP["left_knee"], KP["right_knee"]]


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _mean_center(kp, names, frame_h, frame_w, conf_th):
    pts = [kp[KP[n], :2] for n in names if kp[KP[n], 2] >= conf_th]
    if not pts:
        return None, None
    yx = np.mean(pts, axis=0)
    return float(np.clip(yx[1] / frame_w, 0.0, 1.0)), float(np.clip(yx[0] / frame_h, 0.0, 1.0))


def knee_center_normalized(kp, frame_h, frame_w, conf_th, require_both=True):
    """두 무릎 중점 → frame 안 정규화 (x_norm, y_norm).
    require_both=True(기본): 양쪽 무릎이 다 보일 때만 반환. 한쪽만 보이면 (None,None) →
    호출부가 엉덩이 중심으로 폴백 → 한쪽 다리로 카메라가 쏠리는 것 방지.
    require_both=False: 보이는 무릎(한쪽이라도)으로 계산."""
    li, ri = KP["left_knee"], KP["right_knee"]
    lok = kp[li, 2] >= conf_th
    rok = kp[ri, 2] >= conf_th
    if require_both and not (lok and rok):
        return None, None
    return _mean_center(kp, ("left_knee", "right_knee"), frame_h, frame_w, conf_th)


def hip_center_normalized(kp, frame_h, frame_w, conf_th):
    """엉덩이 중점 → 정규화 (x_norm, y_norm). 안 보이면 (None,None). 한쪽만 보이면 그쪽.
    무릎이 한쪽만 보일 때의 폴백 — 엉덩이는 몸통 중심선이라 좌우 쏠림이 적음."""
    return _mean_center(kp, ("left_hip", "right_hip"), frame_h, frame_w, conf_th)


def enable_torque_safe(ser, servo_id):
    """현재 위치로 goal 동기화 후 torque ON — 켜지는 순간 점프 방지 (실기 사고 재발 방지)."""
    cur = bus.read_position_deg(ser, servo_id)
    bus.write_pos_ex(ser, servo_id, cur, speed=SPEED, acc=ACC)
    bus.write_byte(ser, servo_id, bus.ADDR_TORQUE_ENABLE, 1)
    return cur


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default="COM9", help="서보 버스 시리얼 포트 (기본 COM9)")
    ap.add_argument("--baud", type=int, default=1_000_000)
    ap.add_argument("--model", default=str(Path(__file__).resolve().parent.parent / "models" / "movenet_thunder_int8.tflite"))
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--conf", type=float, default=0.3)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--drive", action="store_true", help="실제로 서보 구동 (없으면 dry-run)")
    ap.add_argument("--yaw-sign", type=int, default=1, choices=[-1, 1])
    ap.add_argument("--pitch-sign", type=int, default=1, choices=[-1, 1])
    ap.add_argument("--axis", choices=["both", "yaw", "pitch"], default="both",
                    help="구동할 축 (방향 시험은 한 축씩 하는 게 깔끔)")
    ap.add_argument("--target", choices=["knee", "hip", "weighted"], default="knee",
                    help="추적 목표점 (knee=양무릎중점→엉덩이폴백 / hip=엉덩이 / weighted=몸통가중)")
    ap.add_argument("--one-knee", action="store_true",
                    help="한쪽 무릎만 보여도 그 무릎으로 추적 (기본: 양쪽 다 보일 때만, 아니면 엉덩이)")
    ap.add_argument("--lock-frames", type=int, default=LOCK_FRAMES,
                    help="중앙에 N프레임 머무르면 잠금(정지). 0=잠금 비활성(계속 추적)")
    ap.add_argument("--reengage", type=float, default=REENGAGE, help="잠금 해제 임계(오차)")
    ap.add_argument("--smooth", type=float, default=SMOOTH_ALPHA, help="목표점 EMA 계수(0~1)")
    ap.add_argument("--deadzone", type=float, default=DEADZONE, help="pitch 데드존(yaw는 섹터 밴드 사용)")
    ap.add_argument("--track-scale", type=float, default=TRACK_SCALE, help="추적 속도 배율 (기본 0.5=현재 1/2)")
    ap.add_argument("--both-knee-scale", type=float, default=BOTH_KNEE_SCALE, help="양 무릎 보일 때 추가 속도 배율 (기본 0.5)")
    ap.add_argument("--sector-side", type=float, default=SECTOR_SIDE, help="좌우 섹터 폭 (기본 1/6, 중앙 4/6 밴드)")
    # 스쿼트 카운팅 (src/exercise_counter.py SquatCounter 재사용)
    ap.add_argument("--squat-down-th", type=float, default=100.0, help="무릎 각도 이 아래면 앉음")
    ap.add_argument("--squat-up-th", type=float, default=140.0, help="무릎 각도 이 위면 일어섬")
    ap.add_argument("--min-dwell-ms", type=float, default=200.0, help="상태 전환 최소 유지(지터 방지)")
    ap.add_argument("--side", choices=["left", "right", "avg", "better"], default="better",
                    help="카운터 입력 무릎 각도 좌/우 선택")
    ap.add_argument("--no-count", action="store_true", help="스쿼트 카운팅 끄기")
    ap.add_argument("--no-window", action="store_true", help="미리보기 창 없이 (헤드리스)")
    ap.add_argument("--max-frames", type=int, default=0, help="N프레임 후 자동 종료 (0=무제한)")
    args = ap.parse_args()

    model_path = Path(args.model)
    if not model_path.exists():
        sys.exit(f"ERROR: model not found: {model_path}")

    itp = tflite.Interpreter(model_path=str(model_path), num_threads=args.threads)
    itp.allocate_tensors()
    in_d = itp.get_input_details()[0]
    out_d = itp.get_output_details()[0]
    _, h_in, w_in, _ = (int(x) for x in in_d["shape"])
    assert h_in == w_in, f"expected square input, got {h_in}x{w_in}"

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        sys.exit(f"ERROR: cannot open camera index {args.camera}")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    aw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    ah = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    ser = None
    yaw_t, pitch_t = YAW_CENTER, PITCH_CENTER
    if args.drive:
        ser = bus.serial.Serial(args.port, args.baud, timeout=0.3)
        # 현재 위치로 torque를 안전하게 켠 뒤 → 항상 중앙(180/180)으로 이동시켜 시작
        cur_yaw = enable_torque_safe(ser, YAW_ID)
        cur_pitch = enable_torque_safe(ser, PITCH_ID)
        bus.write_pos_ex(ser, YAW_ID, YAW_CENTER, speed=SPEED, acc=ACC)
        bus.write_pos_ex(ser, PITCH_ID, PITCH_CENTER, speed=SPEED, acc=ACC)
        deg_per_s = SPEED / bus.TICKS_PER_DEG
        settle = min(3.0, max(abs(cur_yaw - YAW_CENTER), abs(cur_pitch - PITCH_CENTER)) / max(deg_per_s, 1e-6) + 0.4)
        time.sleep(settle)   # 중앙 도착 대기 (이동 거리 비례)
        yaw_t, pitch_t = YAW_CENTER, PITCH_CENTER
        print(f"[drive] torque ON, 중앙({YAW_CENTER:.0f}/{PITCH_CENTER:.0f}) 이동 후 시작 (settle {settle:.1f}s)")

    print("== PTZ camera track ==")
    print(f"  model  : {model_path.name} ({w_in}x{h_in})")
    print(f"  camera : {aw}x{ah} (index {args.camera})")
    print(f"  target : {args.target}  axis={args.axis}  lock_frames={args.lock_frames}")
    print(f"  mode   : {'DRIVE' if args.drive else 'DRY-RUN (서보 정지)'}  yaw_sign={args.yaw_sign} pitch_sign={args.pitch_sign}")
    if not args.no_window:
        print("  q 키로 종료\n")

    dz = args.deadzone
    last_cmd = 0.0
    frame_idx = 0
    smooth_x = smooth_y = None
    centered = 0
    locked = False
    t_prev = time.perf_counter()
    fps = 0.0
    squat = None if args.no_count else SquatCounter(
        args.squat_down_th, args.squat_up_th, args.min_dwell_ms)
    knee_deg = None

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(0.03)
                continue
            frame_idx += 1

            padded, pad_info = letterbox_square(frame, target=h_in)
            rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
            x = np.expand_dims(rgb.astype(np.uint8), 0)
            itp.set_tensor(in_d["index"], x)
            itp.invoke()
            raw = itp.get_tensor(out_d["index"])  # [1,1,17,3]
            kp = unletterbox_kp(raw[0, 0], pad_info, target=h_in)

            # 목표점: 기본 두 무릎 중점. 안 보이면 가중 중심 폴백.
            if args.target == "knee":
                # 양쪽 무릎 → (한쪽만/없음) 엉덩이 중심 → 그래도 없으면 몸통 중심
                tx, ty = knee_center_normalized(kp, ah, aw, args.conf, require_both=not args.one_knee)
                if tx is None:
                    tx, ty = hip_center_normalized(kp, ah, aw, args.conf)
                if tx is None:
                    tx, ty = person_center_normalized(kp, ah, aw, args.conf)
            elif args.target == "hip":
                tx, ty = hip_center_normalized(kp, ah, aw, args.conf)
                if tx is None:
                    tx, ty = person_center_normalized(kp, ah, aw, args.conf)
            else:
                tx, ty = person_center_weighted(kp, ah, aw, args.conf)

            now = time.perf_counter() * 1000.0
            ex = ey = None
            moved = False
            do_yaw = args.axis in ("both", "yaw")
            do_pitch = args.axis in ("both", "pitch")

            # === 스쿼트 rep 카운팅 (무릎 hip-knee-ankle 각도) ===
            rep_event = None
            if squat is not None:
                knee_deg = pick_angle(knee_angle(kp, "left", args.conf),
                                      knee_angle(kp, "right", args.conf),
                                      mode=args.side)
                rep_event = squat.update(knee_deg, now_ms=now)
                if rep_event:
                    print(f"  ★ SQUAT REP #{rep_event[1]}  bottom={rep_event[2]:.0f}deg  (frame {frame_idx})")

            if tx is not None:
                # EMA 스무딩 (키포인트 지터 완화)
                smooth_x = tx if smooth_x is None else args.smooth * tx + (1 - args.smooth) * smooth_x
                smooth_y = ty if smooth_y is None else args.smooth * ty + (1 - args.smooth) * smooth_y
                ex = smooth_x - 0.5
                ey = smooth_y - 0.5

                # 속도 배율: 기본 track_scale, 양 무릎이 다 보이면 추가로 곱(더 천천히)
                both_knees = (kp[KP["left_knee"], 2] >= args.conf and
                              kp[KP["right_knee"], 2] >= args.conf)
                scale = args.track_scale * (args.both_knee_scale if both_knees else 1.0)

                # yaw: 중앙 4/6 밴드 안이면 정지. 양 무릎이 다 보이면 두 무릎 모두 밴드 안이어야 함.
                band = args.sector_side
                yaw_dead = 0.5 - band                        # 중앙 4/6 → 반폭 1/3
                knees_in_band = True
                if both_knees:
                    lx = kp[KP["left_knee"], 1] / aw
                    rx = kp[KP["right_knee"], 1] / aw
                    knees_in_band = (band <= lx <= 1 - band) and (band <= rx <= 1 - band)
                yaw_out = (abs(ex) > yaw_dead) or (not knees_in_band)
                pitch_out = abs(ey) > dz
                active_out = (do_yaw and yaw_out) or (do_pitch and pitch_out)

                if locked:
                    # 잠금 해제(히스테리시스): 밴드보다 조금 더 벗어나야 재추적
                    yaw_re = (abs(ex) > yaw_dead + YAW_REENGAGE_HYST) or (not knees_in_band)
                    pitch_re = abs(ey) > args.reengage
                    if (do_yaw and yaw_re) or (do_pitch and pitch_re):
                        locked = False
                        centered = 0
                else:
                    if do_yaw and yaw_out:
                        step = clamp(GAIN * ex, -MAX_STEP, MAX_STEP) * scale
                        yaw_t = clamp(yaw_t + args.yaw_sign * step, YAW_MIN, YAW_MAX)
                    if do_pitch and pitch_out:
                        step = clamp(GAIN * ey, -MAX_STEP, MAX_STEP) * scale
                        pitch_t = clamp(pitch_t + args.pitch_sign * step, PITCH_MIN, PITCH_MAX)
                    # 목표가 존 안에 연속으로 머무르면 잠금
                    if args.lock_frames > 0 and not active_out:
                        centered += 1
                        if centered >= args.lock_frames:
                            locked = True
                    else:
                        centered = 0
                    if args.drive and (now - last_cmd) > COOLDOWN_MS:
                        if do_yaw:
                            yaw_t = clamp(yaw_t, YAW_MIN, YAW_MAX)
                            bus.write_pos_ex(ser, YAW_ID, yaw_t, speed=SPEED, acc=ACC)
                        if do_pitch:
                            pitch_t = clamp(pitch_t, PITCH_MIN, PITCH_MAX)
                            bus.write_pos_ex(ser, PITCH_ID, pitch_t, speed=SPEED, acc=ACC)
                        last_cmd = now
                        moved = True

            # FPS
            t_now = time.perf_counter()
            dt = t_now - t_prev
            t_prev = t_now
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / dt)

            if not args.no_window:
                annotated = frame.copy()
                draw_pose(annotated, kp, conf_th=args.conf, highlight=_HL_KNEE)
                cv2.line(annotated, (aw // 2, 0), (aw // 2, ah), (80, 80, 80), 1)
                cv2.line(annotated, (0, ah // 2), (aw, ah // 2), (80, 80, 80), 1)
                # 중앙 4/6 밴드 (무릎 유지 목표 구역)
                bx1, bx2 = int(args.sector_side * aw), int((1 - args.sector_side) * aw)
                cv2.line(annotated, (bx1, 0), (bx1, ah), (0, 180, 180), 1)
                cv2.line(annotated, (bx2, 0), (bx2, ah), (0, 180, 180), 1)
                if smooth_x is not None:
                    cx, cy = int(smooth_x * aw), int(smooth_y * ah)
                    dot = (255, 0, 255) if locked else (0, 0, 255)
                    cv2.circle(annotated, (cx, cy), 9, dot, 2, cv2.LINE_AA)
                state = "LOCK" if locked else ("DRIVE" if args.drive else "DRY")
                col = (255, 0, 255) if locked else (0, 255, 0)
                cv2.putText(annotated, f"{state} fps={fps:4.1f} yaw={yaw_t:5.1f} pitch={pitch_t:5.1f} c={centered}",
                            (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2, cv2.LINE_AA)
                det = "person" if tx is not None else "NO PERSON"
                cv2.putText(annotated, det, (10, ah - 14),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2, cv2.LINE_AA)
                if squat is not None:
                    # rep 완료 순간 강조, 무릎 각도/상태 함께 표시
                    rep_col = (0, 255, 255) if rep_event else (255, 255, 255)
                    cv2.putText(annotated, f"SQUAT {squat.reps}  [{squat.state}]",
                                (aw - 250, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.85, rep_col, 2, cv2.LINE_AA)
                    ktxt = f"knee {knee_deg:.0f}deg" if knee_deg is not None else "knee ?"
                    cv2.putText(annotated, ktxt, (aw - 250, 64),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2, cv2.LINE_AA)
                cv2.imshow("PTZ camera track (q=quit, r=reset reps)", annotated)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                if key == ord("r") and squat is not None:
                    squat.reset()
                    print("  [reset] 스쿼트 카운트 0으로 초기화")

            if args.no_window and frame_idx % 5 == 0:
                if tx is not None:
                    st = "LOCK" if locked else "trk "
                    rep_s = f" | squat={squat.reps}[{squat.state}] knee={knee_deg:.0f}" if (
                        squat is not None and knee_deg is not None) else ""
                    print(f"[{frame_idx:4d}] {st} fps={fps:4.1f} tgt=({smooth_x:.2f},{smooth_y:.2f}) "
                          f"err=({ex:+.2f},{ey:+.2f}) -> yaw={yaw_t:5.1f} pitch={pitch_t:5.1f} "
                          f"c={centered} {'CMD' if moved else '   '}{rep_s}")
                else:
                    print(f"[{frame_idx:4d}] fps={fps:4.1f} NO PERSON")

            if args.max_frames > 0 and frame_idx >= args.max_frames:
                break
    except KeyboardInterrupt:
        print("\n[stop] interrupted")
    finally:
        cap.release()
        if not args.no_window:
            cv2.destroyAllWindows()
        if ser is not None:
            ser.close()   # torque는 켜둔 채 종료 (현재 위치 유지)
        if squat is not None:
            s = squat.snapshot()
            print(f"[done] frames={frame_idx}  squat reps={s['reps']}  "
                  f"deepest={s['deepest_overall_deg']}deg")
        else:
            print(f"[done] frames={frame_idx}")


if __name__ == "__main__":
    main()
