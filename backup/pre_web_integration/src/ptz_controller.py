"""PTZ frame-out 검출 + Arduino 시리얼 송신.

판정:
  1. EDGE  — person_center 가 화면 margin 안쪽에 있음 (예: x<0.15 or x>0.85)
              → 즉시 pan 보정 명령
  2. LOST  — N프레임 연속 미검출 (grace period)
              → 마지막 본 방향으로 pan 시도, 일정 시간 후 search sweep

시리얼 프로토콜 (텍스트 명령, 1줄=1명령, '\\n' 종결) — 하드웨어와 무관하게 고정:
  PAN <delta_deg>\\n        # 현재 pan(=yaw) 각도에 delta_deg 더함 (-180 ~ +180)
  TILT <delta_deg>\\n       # 현재 tilt(=pitch) 각도에 delta_deg 더함
  CENTER\\n                  # pan/tilt 중심 (90/90) 복귀
  PING\\n                    # health check

Arduino 측(ptz/sketch/health_care_ptz.ino)은 ST3215 시리얼 버스 서보를
Bus Servo Adapter로 데이지체인 구동 (어댑터 → yaw ID=1 → pitch ID=2).
PWM 직결이 아니므로 이 파일은 하드웨어 변경과 무관 — 텍스트 프로토콜만 그대로
유지하면 됨. 목표 회전 속도는 기존 STEP_DELAY=20ms/° 기준을 서보 네이티브
speed 파라미터로 환산해 유지 (손가락 끼임 방지 취지).
"""
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

try:
    import serial  # pyserial
except ImportError:
    serial = None


class TrackState(Enum):
    IN_FRAME = "in_frame"      # 사람 중앙 영역에 있음, 명령 없음
    EDGE = "edge"              # 가장자리 — pan 보정 진행
    LOST = "lost"              # 미검출 grace 통과 — search/last-direction


@dataclass
class PTZController:
    serial_port: Optional[str] = None
    baudrate: int = 115200
    frame_out_margin: float = 0.15      # 화면 가장자리 N% 안쪽이면 EDGE
    frame_out_grace: int = 15           # 미검출 N프레임 후 LOST
    pan_step_deg: float = 8.0           # EDGE 한 명령당 pan delta
    tilt_step_deg: float = 5.0
    command_cooldown_ms: float = 400.0  # 명령 사이 최소 간격 — 서보 follow-up

    # 내부 상태
    _ser: Optional[object] = field(default=None, init=False, repr=False)
    _last_cmd_ms: float = field(default=0.0, init=False)
    _miss_frames: int = field(default=0, init=False)
    _last_seen_x: Optional[float] = field(default=None, init=False)
    state: TrackState = field(default=TrackState.IN_FRAME, init=False)
    n_pan_cmds: int = field(default=0, init=False)
    n_tilt_cmds: int = field(default=0, init=False)
    enabled: bool = field(default=False, init=False)
    auto_track_enabled: bool = field(default=True, init=False)
    pan_deg: float = field(default=90.0, init=False)
    tilt_deg: float = field(default=90.0, init=False)

    def open(self):
        """시리얼 열기. 미지정 또는 pyserial 부재 시 disabled 모드로 동작 (No-op)."""
        if not self.serial_port:
            print("[ptz] serial_port not specified — disabled (detection only)")
            return False
        if serial is None:
            print("[ptz] pyserial not installed — disabled")
            return False
        try:
            self._ser = serial.Serial(self.serial_port, self.baudrate, timeout=0.2)
            time.sleep(2.0)  # Arduino 재시작 후 boot loader 통과 대기
            self._ser.reset_input_buffer()
            self.enabled = True
            print(f"[ptz] serial open: {self.serial_port} @ {self.baudrate}")
            return True
        except Exception as e:
            print(f"[ptz] serial open FAILED ({e}) — disabled")
            self._ser = None
            return False

    def close(self):
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None

    def _send(self, line: str) -> bool:
        if not self.enabled or self._ser is None:
            return False
        try:
            self._ser.write((line + "\n").encode("ascii"))
            self._ser.flush()
            return True
        except Exception as e:
            print(f"[ptz] write error: {e}")
            return False

    def center(self):
        self._send("CENTER")
        self.pan_deg = 90.0
        self.tilt_deg = 90.0

    def set_auto_track(self, enabled: bool):
        self.auto_track_enabled = bool(enabled)

    def manual_pan(self, delta_deg: float):
        """운영자 직접 조작. cooldown과 무관하게 즉시 전송, 각도만 클램프."""
        delta_deg = max(-10.0, min(10.0, float(delta_deg)))
        self.pan_deg = max(0.0, min(180.0, self.pan_deg + delta_deg))
        self._send(f"PAN {delta_deg:+.1f}")
        self.n_pan_cmds += 1
        self._last_cmd_ms = time.perf_counter() * 1000.0

    def manual_tilt(self, delta_deg: float):
        delta_deg = max(-10.0, min(10.0, float(delta_deg)))
        self.tilt_deg = max(0.0, min(180.0, self.tilt_deg + delta_deg))
        self._send(f"TILT {delta_deg:+.1f}")
        self.n_tilt_cmds += 1
        self._last_cmd_ms = time.perf_counter() * 1000.0

    def manual_center(self):
        self.center()

    def update(self, x_norm: Optional[float], y_norm: Optional[float], now_ms: float):
        """매 프레임 호출. x_norm, y_norm = person_center (None = 미검출).
        auto_track_enabled=False면 상태(EDGE/LOST)만 갱신하고 명령은 보내지 않음
        — 운영자가 수동 제어 중일 때 자동 추적이 명령을 끼워넣지 않도록 함.
        반환: 발행된 명령 (str) 또는 None.
        """
        # 1. detection 상태 갱신
        if x_norm is None:
            self._miss_frames += 1
            if self._miss_frames >= self.frame_out_grace:
                self.state = TrackState.LOST
            # IN_FRAME 또는 EDGE 상태 유지 (grace 이내)
        else:
            self._miss_frames = 0
            self._last_seen_x = x_norm
            if (x_norm < self.frame_out_margin or x_norm > 1.0 - self.frame_out_margin
                    or y_norm < self.frame_out_margin or y_norm > 1.0 - self.frame_out_margin):
                self.state = TrackState.EDGE
            else:
                self.state = TrackState.IN_FRAME

        # 2. 수동 제어 모드면 자동 명령 생성 안 함 (상태 표시만 갱신)
        if not self.auto_track_enabled:
            return None

        # 3. cooldown 확인 — 서보가 명령을 소화할 시간 (~ 명령당 8° × 20ms/° = 160ms 이상)
        if now_ms - self._last_cmd_ms < self.command_cooldown_ms:
            return None

        # 3. 상태별 명령 결정
        cmd = None
        if self.state == TrackState.EDGE and x_norm is not None:
            dx = x_norm - 0.5
            dy = y_norm - 0.5
            if abs(dx) > self.frame_out_margin:
                # 사람이 오른쪽이면 카메라도 오른쪽 회전 — 양수 = 좌측 회전이라 가정
                # 단위: 사람-카메라 offset 정도에 비례, 한 step 최대 pan_step_deg
                delta = -self.pan_step_deg if dx > 0 else self.pan_step_deg
                cmd = f"PAN {delta:+.1f}"
                self.n_pan_cmds += 1
            elif abs(dy) > self.frame_out_margin:
                delta = self.tilt_step_deg if dy > 0 else -self.tilt_step_deg
                cmd = f"TILT {delta:+.1f}"
                self.n_tilt_cmds += 1

        elif self.state == TrackState.LOST:
            # 마지막 본 x_norm 방향으로 pan — 0.5 미만이면 왼쪽 search
            if self._last_seen_x is not None:
                delta = -self.pan_step_deg if self._last_seen_x > 0.5 else self.pan_step_deg
            else:
                delta = self.pan_step_deg  # 방향 정보 없음 — 우측 sweep
            cmd = f"PAN {delta:+.1f}"
            self.n_pan_cmds += 1

        if cmd is not None:
            self._send(cmd)
            self._last_cmd_ms = now_ms
        return cmd

    def snapshot(self) -> dict:
        return {
            "enabled": self.enabled,
            "state": self.state.value,
            "miss_frames": self._miss_frames,
            "last_seen_x": round(self._last_seen_x, 3) if self._last_seen_x is not None else None,
            "pan_cmds_total": self.n_pan_cmds,
            "tilt_cmds_total": self.n_tilt_cmds,
            "margin": self.frame_out_margin,
            "grace_frames": self.frame_out_grace,
            "auto_track_enabled": self.auto_track_enabled,
            "pan_deg": round(self.pan_deg, 1),
            "tilt_deg": round(self.tilt_deg, 1),
        }
