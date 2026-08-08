"""PTZ 추적 컨트롤러 - ST3215 시리얼 버스 서보 직접 구동 (MCU 경유 아님).

추적 로직 (scripts/ptz_camera_track.py v2에서 실기 검증된 것을 이식):
  - 목표점: 두 무릎 중점(양쪽 다 보일 때) → 엉덩이 중심 → 몸통 중심 폴백.
    한쪽 무릎만 보일 때 그 다리로 카메라가 쏠리는 것을 방지.
  - EMA 스무딩으로 키포인트 지터 완화.
  - yaw: 화면을 좌 1/6 · 중앙 4/6 · 우 1/6 로 나눠, 목표(+양 무릎)가 중앙 4/6
    밴드 안이면 정지. 밖으로 나가야 팬.
  - pitch: 데드존 기반 (목표 y 기준점은 pitch_target_y, 기본 화면 중앙 0.5).
  - 획득→잠금: 존 안에 lock_frames 연속 머물면 LOCK(명령 정지), 재개는
    히스테리시스로 충분히 벗어날 때만 → 미세 흔들림(도리도리) 제거.
  - 속도: track_scale(기본 1/2), 양 무릎 다 보이면 both_knee_scale 추가(총 1/4).

안전:
  - 모든 서보 명령은 소프트리밋으로 클램프 (yaw 중앙±90, pitch 중앙±30 - 실측값).
  - 안전속도(≈569 tick/s = 20ms/° 등가) 고정 - 손가락 끼임 방지.
  - torque는 항상 "현재 위치로 goal 동기화 → ON" 순서로 켬 (켜지는 순간 점프 방지).
  - 시작 시 중앙으로 정렬 후 추적 시작.

시리얼 미지정/열기 실패/서보 무응답이면 disabled 모드 - 추적 상태 계산만 하고
서보 명령은 안 보냄 (웹 UI는 그대로 동작).
"""
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from pose_utils import (
    KP, knee_center_normalized, hip_center_normalized, person_center_normalized,
    shoulder_center_normalized,
)

try:
    import st3215_bus as bus
except Exception:  # pyserial 부재 등
    bus = None


class TrackState(Enum):
    IN_FRAME = "in_frame"      # 목표가 존 안 (또는 잠금) - 명령 없음
    EDGE = "edge"              # 존 밖 - 추적 중
    LOST = "lost"              # 미검출 grace 통과


@dataclass
class PTZController:
    # 연결
    serial_port: Optional[str] = None
    baudrate: int = 1_000_000            # ST3215 버스 기본 baud
    yaw_id: int = 1
    pitch_id: int = 2

    # 각도 컨벤션 (tick 2047 캘리브레이션 = 180°), 실측 가동범위
    yaw_center: float = 180.0
    yaw_min: float = 90.0
    yaw_max: float = 270.0
    pitch_center: float = 180.0
    pitch_min: float = 150.0
    pitch_max: float = 210.0

    # 추적 파라미터
    conf_th: float = 0.3
    sector_side: float = 1.0 / 6.0       # 좌우 섹터 각 1/6 → 중앙 4/6 밴드
    # pitch는 무릎 높이를 쫓지 않는다: 스쿼트 중 무릎이 상하로 크게 움직이므로
    # 좁은 데드존이면 카메라가 매 rep마다 끄덕인다. 기준점을 하단쪽(0.62)에 두고
    # 데드존을 넓게 잡아 "큰 프레이밍 오차"만 교정한다.
    pitch_deadzone: float = 0.20
    pitch_target_y: float = 0.62         # pitch 세로 기준점 (무릎이 화면 하단 1/3쯤)
    # 상체 모드(숄더프레스/레터럴): 무릎 대신 어깨를 추적하고, 어깨를 화면
    # 하단쪽(pitch_target_y_upper)에 둬 머리 위로 든 팔이 프레임 밖으로 잘리지
    # 않게 한다. 어깨는 상하로 거의 안 흔들리므로 데드존은 좁게. main.py가
    # set_track_mode()로 운동 종목에 맞춰 넘긴다.
    pitch_target_y_upper: float = 0.64
    pitch_deadzone_upper: float = 0.15
    # 경비 모드: 운동이 아니라 사람 전신을 화면 중앙 부근에 두는 게 목적이라
    # 무릎/어깨 우선순위 없이 person_center_normalized(어깨+엉덩이 평균)를 바로 쓴다.
    pitch_target_y_guard: float = 0.50
    pitch_deadzone_guard: float = 0.20
    guard_home_after_s: float = 10.0     # 경비 모드에서 이 시간 이상 미검출이면 홈(중앙)으로 복귀
    track_mode: str = "lower"            # "lower"(스쿼트: 무릎) | "upper"(상체: 어깨) | "guard"(전신)
    reengage: float = 0.18
    yaw_reengage_hyst: float = 0.05
    lock_frames: int = 10
    smooth_alpha: float = 0.4
    # 추적 속도는 deg/s로 직접 표현한다 (프레임 수와 무관).
    # 원래는 "프레임당 도수"(gain=8.0, max_step=4.0 deg/frame)였는데, 이 값이
    # 개발 PC(~29 FPS) 기준이라 11 FPS인 UNO Q에서는 각속도가 1/2.6로 떨어져
    # 서보가 22ms 움직이고 228ms 멈추는 "톡톡" 끊김이 생겼다. 아래 값은 기존
    # 튜닝에 29를 곱해 환산한 것이라 PC 동작은 그대로 유지된다.
    gain_deg_per_s: float = 232.0        # 정규화 오차 1.0당 각속도 (8.0 x 29)
    max_deg_per_s: float = 116.0         # 오차가 커도 이 이상은 안 돈다 (4.0 x 29)
    track_scale: float = 0.5             # 추적 속도 1/2
    both_knee_scale: float = 0.5         # 양 무릎 보이면 추가 1/2 (총 1/4)
    # -> 양 무릎이 보일 때 실제 상한은 116 x 0.5 x 0.5 = 29 deg/s
    max_dt_s: float = 0.15               # dt 상한 - LOST 복귀 직후 튀는 것 방지
    yaw_sign: int = 1
    pitch_sign: int = -1  # 2026-08-07 재조립 이후 확정값 (실측 확인됨) - 재조립 전엔 1
    frame_out_grace: int = 15            # 미검출 N프레임 후 LOST
    # 추적 손실 복구 사다리 (yaw 전용, pitch는 그대로 둔다)
    #   관성 -> 그 자리 대기 -> 관성 이전으로 복귀 후 대기 -> 중앙 복귀 후 정지
    # 어느 단계든 재검출되면 즉시 취소하고 정상 추적으로 돌아간다.
    # 관성 방향/속도는 "마지막 yaw 각속도"를 쓴다. 사람이 중앙에 가만히 있어
    # 카메라가 안 움직이던 중이면 속도가 0이라 관성이 아예 안 걸린다 —
    # 검출만 깜빡인 경우의 헛발질이 이 규칙으로 자연히 걸러진다.
    coast_start_misses: int = 3          # 단발 깜빡임 무시 - 연속 N프레임부터 관성
    # 관성 지속 "프레임 수" — 시간이 아니라 프레임이므로 FPS가 다르면 지속 시간과
    # 이동 거리가 달라진다 (11 FPS에서 15프레임 = 1.36초, 29 FPS면 0.52초).
    # 알려진 한계로 남겨둔 부분. 상세: docs/history/2026-07-19_02
    coast_frames: int = 15               # 11 FPS 기준 약 1.36초
    # 프레임당 속도 감쇠. 1.0이면 감쇠 없이 등속으로 끝까지 돌다 딱 멈춘다.
    # 관성 이동 "거리"를 결정하는 지배적 인자 (coast_frames는 거의 영향 없음):
    #   0.8 -> 27도, 0.9 -> 44도, 1.0 -> 84도  (15프레임, 11 FPS 기준)
    coast_decay: float = 0.9
    coast_hold_s: float = 1.0            # 관성 끝 지점에서 대기
    return_hold_s: float = 2.0           # 관성 이전 위치에서 대기
    # 화면 내 이동량(정규화 0~1)을 각도로 환산하는 계수 = 카메라 수평 화각.
    # 정확한 값을 모르면 대략 60도로 두고 실측으로 보정한다 (카메라를 알려진
    # 각도만큼 돌려놓고 피사체가 화면에서 몇 % 밀리는지 재면 나온다).
    coast_fov_deg: float = 60.0
    # 서보(50 deg/s)가 목표각이 미는 속도(최대 29 deg/s)보다 1.7배 빠르다.
    # 250ms 주기로 던지면 서보가 먼저 도착해 주기의 40~70%를 멈춰 있어서
    # "톡톡" 끊겨 보인다. 프레임 간격(11 FPS = 91ms)보다 짧게 줘서 사실상
    # 매 프레임 갱신되게 한다. 1Mbaud에 명령 15바이트라 버스 부하는 무시 가능.
    command_cooldown_ms: float = 80.0
    servo_speed: int = 569               # 안전속도
    servo_acc: int = 20

    # 내부 상태
    _ser: Optional[object] = field(default=None, init=False, repr=False)
    _last_cmd_ms: float = field(default=0.0, init=False)
    _last_update_ms: Optional[float] = field(default=None, init=False)
    _last_yaw_vel: float = field(default=0.0, init=False)      # 마지막 yaw 각속도 (deg/s, 부호 포함)
    _prev_smooth_x: Optional[float] = field(default=None, init=False)
    _last_subject_vel: float = field(default=0.0, init=False)  # 화면 내 피사체 속도 (정규화 x/초)
    _recover_stage: str = field(default="none", init=False)    # none|coast|hold|returned|centered
    _coast_vel: float = field(default=0.0, init=False)
    _coast_left: int = field(default=0, init=False)
    _pre_coast_pan: Optional[float] = field(default=None, init=False)
    _stage_since_ms: float = field(default=0.0, init=False)
    _miss_frames: int = field(default=0, init=False)
    _smooth_x: Optional[float] = field(default=None, init=False)
    _smooth_y: Optional[float] = field(default=None, init=False)
    _centered: int = field(default=0, init=False)
    _guard_lost_since_ms: Optional[float] = field(default=None, init=False)   # 경비 모드 - 미검출 시작 시각
    _guard_at_home: bool = field(default=True, init=False)                   # 경비 모드 - 이미 홈으로 보냈는지
    locked: bool = field(default=False, init=False)
    state: TrackState = field(default=TrackState.IN_FRAME, init=False)
    n_pan_cmds: int = field(default=0, init=False)
    n_tilt_cmds: int = field(default=0, init=False)
    enabled: bool = field(default=False, init=False)
    auto_track_enabled: bool = field(default=True, init=False)
    pan_deg: float = field(default=180.0, init=False)   # yaw 절대각 (중앙 180)
    tilt_deg: float = field(default=180.0, init=False)  # pitch 절대각 (중앙 180)

    # ---------- 연결 / 종료 ----------

    def open(self) -> bool:
        """서보 버스 연결 + torque 안전 ON + 중앙 정렬. 실패 시 disabled 모드."""
        self.pan_deg, self.tilt_deg = self.yaw_center, self.pitch_center
        if not self.serial_port:
            print("[ptz] serial_port 미지정 - disabled (추적 계산만)")
            return False
        if bus is None:
            print("[ptz] st3215_bus 사용 불가(pyserial?) - disabled")
            return False
        try:
            self._ser = bus.serial.Serial(self.serial_port, self.baudrate, timeout=0.3)
        except Exception as e:
            print(f"[ptz] 포트 열기 실패 ({e}) - disabled")
            self._ser = None
            return False
        # 서보 응답 확인 - 전원/배선 문제면 여기서 걸러 disabled 로 떨어뜨림
        try:
            bus.ping(self._ser, self.yaw_id)
            bus.ping(self._ser, self.pitch_id)
        except Exception as e:
            print(f"[ptz] 서보 무응답 ({e}) - 서보 전원/버스 케이블 확인. disabled")
            self.close()
            return False

        self.enabled = True
        cur_y = self._torque_on_safe(self.yaw_id)
        cur_p = self._torque_on_safe(self.pitch_id)
        self._write(self.yaw_id, self.yaw_center)
        self._write(self.pitch_id, self.pitch_center)
        deg_per_s = self.servo_speed / bus.TICKS_PER_DEG
        settle = min(3.0, max(abs(cur_y - self.yaw_center),
                              abs(cur_p - self.pitch_center)) / max(deg_per_s, 1e-6) + 0.4)
        time.sleep(settle)
        self.pan_deg, self.tilt_deg = self.yaw_center, self.pitch_center
        print(f"[ptz] 버스 연결 {self.serial_port} @ {self.baudrate}, "
              f"중앙({self.yaw_center:.0f}/{self.pitch_center:.0f}) 정렬 후 시작")
        return True

    def close(self):
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None
        self.enabled = False

    # ---------- 저수준 서보 ----------

    def _torque_on_safe(self, servo_id: int) -> float:
        """현재 위치로 goal 동기화 후 torque ON - 켜지는 순간 점프 방지."""
        cur = bus.read_position_deg(self._ser, servo_id)
        bus.write_pos_ex(self._ser, servo_id, cur, speed=self.servo_speed, acc=self.servo_acc)
        bus.write_byte(self._ser, servo_id, bus.ADDR_TORQUE_ENABLE, 1)
        return cur

    def _write(self, servo_id: int, deg: float) -> bool:
        if not self.enabled or self._ser is None:
            return False
        try:
            bus.write_pos_ex(self._ser, servo_id, deg, speed=self.servo_speed, acc=self.servo_acc)
            return True
        except Exception as e:
            print(f"[ptz] 서보 쓰기 오류: {e}")
            return False

    @staticmethod
    def _clamp(v, lo, hi):
        return max(lo, min(hi, v))

    # ---------- 수동 조작 (웹 /api/ptz) ----------

    def set_auto_track(self, enabled: bool):
        self.auto_track_enabled = bool(enabled)

    def set_track_mode(self, exercise_or_mode: str):
        """운동 종목(또는 'guard')에 맞춰 추적 타깃/프레이밍 전환.
        overhead/lateral(또는 'upper') → 상체(어깨 중점), guard → 전신(사람 중심),
        그 외 → 하체(무릎 중점).

        모드가 실제로 바뀌는 순간에는 잠금을 강제로 푼다. 안 그러면 스쿼트에서
        무릎을 잠그고 정지해 있던 카메라가 상체 모드로 바뀐 뒤에도 새 타깃(어깨)과의
        오차가 reengage 히스테리시스를 못 넘으면 계속 잠긴 채 안 움직인다 - 무릎/어깨
        기본 타깃 y가 프레임상 비슷하게 잡히도록 설계돼 있어 이 케이스가 흔하다.

        guard로 "진입"하는 순간에는 추가로 즉시 홈(중앙)으로 정렬한다 - 경비 모드는
        기본적으로 홈 자세를 유지하다가 사람이 나타나면 추적하는 것이라, 직전
        운동 모드에서 어디를 보고 있었든 상관없이 항상 같은 자세로 시작해야 한다."""
        new_mode = "guard" if exercise_or_mode == "guard" else (
            "upper" if exercise_or_mode in ("upper", "overhead", "lateral") else "lower")
        if new_mode != self.track_mode:
            self.track_mode = new_mode
            self.locked = False
            self._centered = 0
            if new_mode == "guard":
                self.center()
                self._guard_lost_since_ms = None
                self._guard_at_home = True

    def manual_pan(self, delta_deg: float):
        """운영자 직접 조작 - cooldown 무관 즉시, 소프트리밋 클램프."""
        delta_deg = self._clamp(float(delta_deg), -10.0, 10.0)
        self.pan_deg = self._clamp(self.pan_deg + self.yaw_sign * delta_deg, self.yaw_min, self.yaw_max)
        self._write(self.yaw_id, self.pan_deg)
        self.n_pan_cmds += 1
        self._last_cmd_ms = time.perf_counter() * 1000.0
        self.locked = False
        self._centered = 0

    def manual_tilt(self, delta_deg: float):
        delta_deg = self._clamp(float(delta_deg), -10.0, 10.0)
        self.tilt_deg = self._clamp(self.tilt_deg + self.pitch_sign * delta_deg, self.pitch_min, self.pitch_max)
        self._write(self.pitch_id, self.tilt_deg)
        self.n_tilt_cmds += 1
        self._last_cmd_ms = time.perf_counter() * 1000.0
        self.locked = False
        self._centered = 0

    def center(self):
        self.pan_deg, self.tilt_deg = self.yaw_center, self.pitch_center
        self._write(self.yaw_id, self.pan_deg)
        self._write(self.pitch_id, self.tilt_deg)
        self.locked = False
        self._centered = 0

    def manual_center(self):
        self.center()

    # ---------- 추적 ----------

    def _target(self, kp, frame_h, frame_w):
        """추적 목표점.
        guard(경비): 사람 전신 중심(어깨+엉덩이 평균) - 무릎/어깨 우선순위 없음.
        lower(스쿼트): 두 무릎 중점 → 엉덩이 → 몸통.
        upper(상체): 두 어깨 중점 → 엉덩이 → 몸통 (머리 위 팔을 위해 상체 추적)."""
        if self.track_mode == "guard":
            return person_center_normalized(kp, frame_h, frame_w, self.conf_th)
        if self.track_mode == "upper":
            tx, ty = shoulder_center_normalized(kp, frame_h, frame_w, self.conf_th)
        else:
            tx, ty = knee_center_normalized(kp, frame_h, frame_w, self.conf_th, require_both=True)
        if tx is None:
            tx, ty = hip_center_normalized(kp, frame_h, frame_w, self.conf_th)
        if tx is None:
            tx, ty = person_center_normalized(kp, frame_h, frame_w, self.conf_th)
        return tx, ty

    # ---------- 추적 손실 복구 (yaw 전용) ----------

    def _emit_yaw(self, now_ms: float, tag: str, force: bool = False) -> Optional[str]:
        """복구 동작의 yaw 목표를 서보에 반영. force면 쿨다운 무시(1회성 이동)."""
        if not force and now_ms - self._last_cmd_ms < self.command_cooldown_ms:
            return None
        if self._write(self.yaw_id, self.pan_deg):
            self.n_pan_cmds += 1
        self._last_cmd_ms = now_ms
        return f"{tag} {self.pan_deg:.1f}"

    def _reset_recovery(self):
        """재검출 시 복구 사다리를 통째로 취소하고 정상 추적으로 되돌린다."""
        self._recover_stage = "none"
        self._coast_vel = 0.0
        self._coast_left = 0
        self._pre_coast_pan = None

    def _recover_yaw(self, now_ms: float, dt_s: float) -> Optional[str]:
        """미검출 구간에서만 호출. 사다리를 한 단계씩 진행한다.
        coast -> hold -> returned -> centered 순이며, 각 단계는 재검출되면
        _reset_recovery()로 즉시 취소된다."""
        if self._miss_frames < self.coast_start_misses:
            return None                  # 단발 깜빡임 - 아직 아무것도 안 함

        if self._recover_stage == "none":
            self._pre_coast_pan = self.pan_deg
            # 사람의 실제 각속도 = 카메라가 이미 돌던 속도 + 화면에 남은 이동량.
            # 둘 중 하나만 보면 놓친다: 중앙에서 빠르게 이탈하면 카메라는 안
            # 움직였고(전자 0), 카메라가 잘 따라가던 중이면 화면 속 사람은
            # 거의 정지해 보인다(후자 0). 제자리 손실은 둘 다 0이라 관성이
            # 안 걸리고, 이게 헛발질을 막는 성질이다.
            self._coast_vel = self._clamp(
                self._last_yaw_vel + self.yaw_sign * self._last_subject_vel * self.coast_fov_deg,
                -self.max_deg_per_s, self.max_deg_per_s)
            self._coast_left = self.coast_frames if abs(self._coast_vel) > 1.0 else 0
            # 정지 중 손실(각속도 0)이면 관성을 건너뛰고 바로 대기 단계로
            self._recover_stage = "coast" if self._coast_left > 0 else "hold"
            self._stage_since_ms = now_ms

        if self._recover_stage == "coast":
            self.pan_deg = self._clamp(self.pan_deg + self._coast_vel * dt_s,
                                       self.yaw_min, self.yaw_max)
            self._coast_vel *= self.coast_decay
            self._coast_left -= 1
            if self._coast_left <= 0:
                self._recover_stage = "hold"
                self._stage_since_ms = now_ms
            return self._emit_yaw(now_ms, "COAST")

        if self._recover_stage == "hold":
            if now_ms - self._stage_since_ms < self.coast_hold_s * 1000.0:
                return None
            if self._pre_coast_pan is not None:
                self.pan_deg = self._clamp(self._pre_coast_pan, self.yaw_min, self.yaw_max)
            self._recover_stage = "returned"
            self._stage_since_ms = now_ms
            return self._emit_yaw(now_ms, "BACK", force=True)

        if self._recover_stage == "returned":
            if now_ms - self._stage_since_ms < self.return_hold_s * 1000.0:
                return None
            self.pan_deg = self.yaw_center
            self._recover_stage = "centered"
            self._stage_since_ms = now_ms
            return self._emit_yaw(now_ms, "CENTER", force=True)

        return None                      # centered - 사람 찾을 때까지 그대로 대기

    def _guard_home(self, now_ms: float) -> Optional[str]:
        """경비 모드 전용 미검출 처리. 운동 모드의 yaw 관성 사다리(_recover_yaw)
        대신 훨씬 단순한 규칙을 쓴다: guard_home_after_s(기본 10초) 이상
        연속으로 사람을 못 찾으면 pan/tilt를 둘 다 한 번에 홈(중앙)으로 보내고
        멈춘다 - 관성/단계적 복귀 없이, 사람이 없으면 그냥 정위치로 돌아가
        대기하는 게 경비 카메라의 자연스러운 기본 동작이기 때문이다."""
        if self._guard_lost_since_ms is None:
            self._guard_lost_since_ms = now_ms
        if self._guard_at_home:
            return None
        if (now_ms - self._guard_lost_since_ms) / 1000.0 < self.guard_home_after_s:
            return None
        self.pan_deg, self.tilt_deg = self.yaw_center, self.pitch_center
        moved_yaw = self._write(self.yaw_id, self.pan_deg)
        moved_pitch = self._write(self.pitch_id, self.tilt_deg)
        if moved_yaw:
            self.n_pan_cmds += 1
        if moved_pitch:
            self.n_tilt_cmds += 1
        self._last_cmd_ms = now_ms
        self._guard_at_home = True
        self.locked = False
        return "HOME"

    def update(self, kp, frame_h: int, frame_w: int, now_ms: float) -> Optional[str]:
        """매 프레임 호출. kp = MoveNet 17 keypoint (원본 픽셀 y,x,conf).
        반환: 표시용 짧은 문자열 또는 None."""
        # 이번 프레임이 커버하는 시간(초). 각속도(deg/s)에 이걸 곱해 이동량을
        # 낸다. LOST 구간을 건너뛴 직후 dt가 커져 한 번에 튀지 않도록
        # max_dt_s로 자른다. 미검출로 조기 return하는 경로에서도 갱신돼야
        # 하므로 맨 앞에서 처리한다.
        if self._last_update_ms is None:
            dt_s = 0.0                   # 첫 프레임 - 간격을 알 수 없으니 이동 없음
        else:
            dt_s = min(max((now_ms - self._last_update_ms) / 1000.0, 0.0), self.max_dt_s)
        self._last_update_ms = now_ms

        tx, ty = self._target(kp, frame_h, frame_w)

        # 미검출 처리
        if tx is None:
            self._miss_frames += 1
            if self._miss_frames >= self.frame_out_grace:
                self.state = TrackState.LOST
            if self.track_mode == "guard":
                return self._guard_home(now_ms)
            if self.enabled and self.auto_track_enabled:
                return self._recover_yaw(now_ms, dt_s)
            return None
        had_misses = self._miss_frames > 0
        self._miss_frames = 0
        if self.track_mode == "guard":
            self._guard_lost_since_ms = None   # 재검출 - 미검출 타이머 리셋
            self._guard_at_home = False
        else:
            self._reset_recovery()           # 재검출 - 복구 사다리 즉시 취소

        # EMA 스무딩
        a = self.smooth_alpha
        self._smooth_x = tx if self._smooth_x is None else a * tx + (1 - a) * self._smooth_x
        self._smooth_y = ty if self._smooth_y is None else a * ty + (1 - a) * self._smooth_y

        # 화면 내 피사체 속도 (정규화 x/초). 관성이 "카메라가 얼마나 돌고
        # 있었나"가 아니라 "사람이 얼마나 빨리 움직였나"를 근거로 삼기 위함.
        # 손실 구간을 건너뛴 델타는 시간 간격이 불확실해 신뢰할 수 없으므로 버린다.
        if had_misses:
            self._prev_smooth_x = None
        if self._prev_smooth_x is not None and dt_s > 1e-6:
            self._last_subject_vel = (self._smooth_x - self._prev_smooth_x) / dt_s
        else:
            self._last_subject_vel = 0.0
        self._prev_smooth_x = self._smooth_x
        # 모드별 프레이밍: upper(상체)면 어깨를 화면 아래쪽에 둬 머리 위 팔 공간 확보.
        # guard(경비)는 전신을 화면 중앙 부근에 둔다.
        if self.track_mode == "upper":
            pt_y, pdz = self.pitch_target_y_upper, self.pitch_deadzone_upper
        elif self.track_mode == "guard":
            pt_y, pdz = self.pitch_target_y_guard, self.pitch_deadzone_guard
        else:
            pt_y, pdz = self.pitch_target_y, self.pitch_deadzone
        ex = self._smooth_x - 0.5
        ey = self._smooth_y - pt_y

        # 양 무릎 가시 여부 → 속도 배율 + 밴드 판정 (하체 모드에서만)
        both_knees = (self.track_mode == "lower" and
                      kp[KP["left_knee"], 2] >= self.conf_th and
                      kp[KP["right_knee"], 2] >= self.conf_th)
        scale = self.track_scale * (self.both_knee_scale if both_knees else 1.0)

        band = self.sector_side
        yaw_dead = 0.5 - band                     # 중앙 4/6 → 반폭 1/3
        knees_in_band = True
        if both_knees:
            lx = kp[KP["left_knee"], 1] / frame_w
            rx = kp[KP["right_knee"], 1] / frame_w
            knees_in_band = (band <= lx <= 1 - band) and (band <= rx <= 1 - band)
        yaw_out = (abs(ex) > yaw_dead) or (not knees_in_band)
        pitch_out = abs(ey) > pdz

        # 상태 표시
        self.state = TrackState.EDGE if (yaw_out or pitch_out) else TrackState.IN_FRAME

        # 수동 제어 중이면 상태만 갱신
        if not self.auto_track_enabled:
            return None

        if self.locked:
            yaw_re = (abs(ex) > yaw_dead + self.yaw_reengage_hyst) or (not knees_in_band)
            pitch_re = abs(ey) > self.reengage
            if yaw_re or pitch_re:
                self.locked = False
                self._centered = 0
            else:
                self.state = TrackState.IN_FRAME
                self._last_yaw_vel = 0.0     # 잠금 = 정지 중 - 관성 근거 없음
                return None

        # 목표각 갱신
        if yaw_out:
            deg_per_s = self._clamp(self.gain_deg_per_s * ex,
                                    -self.max_deg_per_s, self.max_deg_per_s) * scale
            self.pan_deg = self._clamp(self.pan_deg + self.yaw_sign * deg_per_s * dt_s,
                                       self.yaw_min, self.yaw_max)
            self._last_yaw_vel = self.yaw_sign * deg_per_s   # 관성이 이어받을 각속도
        else:
            self._last_yaw_vel = 0.0     # 데드존 안 = 정지 중
        if pitch_out:
            deg_per_s = self._clamp(self.gain_deg_per_s * ey,
                                    -self.max_deg_per_s, self.max_deg_per_s) * scale
            self.tilt_deg = self._clamp(self.tilt_deg + self.pitch_sign * deg_per_s * dt_s,
                                        self.pitch_min, self.pitch_max)

        # 존 안에 연속으로 머무르면 잠금
        if self.lock_frames > 0 and not (yaw_out or pitch_out):
            self._centered += 1
            if self._centered >= self.lock_frames:
                self.locked = True
        else:
            self._centered = 0

        if now_ms - self._last_cmd_ms < self.command_cooldown_ms:
            return None
        if not (yaw_out or pitch_out):
            return None

        cmd = None
        if yaw_out:
            if self._write(self.yaw_id, self.pan_deg):   # 실제 전송된 것만 집계
                self.n_pan_cmds += 1
            cmd = f"YAW {self.pan_deg:.1f}"
        if pitch_out:
            if self._write(self.pitch_id, self.tilt_deg):
                self.n_tilt_cmds += 1
            cmd = (cmd + " | " if cmd else "") + f"PITCH {self.tilt_deg:.1f}"
        self._last_cmd_ms = now_ms
        return cmd

    def snapshot(self) -> dict:
        return {
            "enabled": self.enabled,
            "state": self.state.value,
            "track_mode": self.track_mode,
            "locked": self.locked,
            "miss_frames": self._miss_frames,
            "guard_at_home": self._guard_at_home if self.track_mode == "guard" else None,
            "target_norm": [
                round(self._smooth_x, 3) if self._smooth_x is not None else None,
                round(self._smooth_y, 3) if self._smooth_y is not None else None,
            ],
            "pan_cmds_total": self.n_pan_cmds,
            "tilt_cmds_total": self.n_tilt_cmds,
            "sector_side": self.sector_side,
            "grace_frames": self.frame_out_grace,
            "auto_track_enabled": self.auto_track_enabled,
            # 절대 서보각 (중앙=180) + 중앙 기준 오프셋
            "pan_deg": round(self.pan_deg, 1),
            "tilt_deg": round(self.tilt_deg, 1),
            "pan_offset_deg": round(self.pan_deg - self.yaw_center, 1),
            "tilt_offset_deg": round(self.tilt_deg - self.pitch_center, 1),
        }
