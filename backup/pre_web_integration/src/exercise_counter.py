"""Rep counter state machine — squat (무릎 각도) / pushup (팔꿈치 각도) 공통 base.

설계:
  UP (각도 > up_th) ↔ DOWN (각도 < down_th)
  UP → DOWN → UP 한 사이클 = 1 rep.

함정 방지:
  - min_dwell_ms : 상태 전환 후 최소 유지 시간 — jitter 떨림 방지
  - hysteresis   : down_th < up_th — 임계 사이 진동에서 카운트 폭발 차단

기존 pose/scripts/squat_counter.py 패턴을 재사용. 종목별 임계값만 다름.
"""
import time
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class RepCounter:
    """일반화된 rep 카운터 — 각도 시계열 → rep 사이클 검출."""
    down_th: float
    up_th: float
    name: str = "rep"
    min_dwell_ms: float = 200.0

    state: str = "UP"
    reps: int = 0
    last_transition_ms: float = 0.0
    min_angle_in_down: Optional[float] = None
    deepest_overall: Optional[float] = None
    last_rep_min_angle: Optional[float] = None

    def update(self, angle_deg: Optional[float], now_ms: Optional[float] = None
               ) -> Optional[Tuple[str, int, float]]:
        """각도 1샘플 → 상태 갱신. rep 완료 시 ('REP', total, bottom_min_angle)."""
        if angle_deg is None:
            return None
        if now_ms is None:
            now_ms = time.perf_counter() * 1000.0

        if self.state == "UP":
            if angle_deg < self.down_th and (now_ms - self.last_transition_ms) >= self.min_dwell_ms:
                self.state = "DOWN"
                self.last_transition_ms = now_ms
                self.min_angle_in_down = angle_deg
            return None

        # DOWN
        if self.min_angle_in_down is None or angle_deg < self.min_angle_in_down:
            self.min_angle_in_down = angle_deg
            if self.deepest_overall is None or angle_deg < self.deepest_overall:
                self.deepest_overall = angle_deg

        if angle_deg > self.up_th and (now_ms - self.last_transition_ms) >= self.min_dwell_ms:
            self.state = "UP"
            self.last_transition_ms = now_ms
            self.reps += 1
            self.last_rep_min_angle = self.min_angle_in_down
            min_now = self.min_angle_in_down if self.min_angle_in_down is not None else angle_deg
            self.min_angle_in_down = None
            return ("REP", self.reps, min_now)
        return None

    def reset(self):
        self.state = "UP"
        self.reps = 0
        self.last_transition_ms = 0.0
        self.min_angle_in_down = None
        self.deepest_overall = None
        self.last_rep_min_angle = None

    def snapshot(self) -> dict:
        return {
            "name": self.name,
            "state": self.state,
            "reps": self.reps,
            "deepest_overall_deg": round(self.deepest_overall, 1) if self.deepest_overall is not None else None,
            "last_rep_min_deg": round(self.last_rep_min_angle, 1) if self.last_rep_min_angle is not None else None,
            "current_down_min_deg": round(self.min_angle_in_down, 1) if self.min_angle_in_down is not None else None,
            "thresholds_deg": {"down": self.down_th, "up": self.up_th},
        }


def SquatCounter(down_th: float = 100.0, up_th: float = 140.0,
                 min_dwell_ms: float = 200.0) -> RepCounter:
    """무릎 각도 hip-knee-ankle 기반.
    down<100 → 앉음, up>140 → 일어섬. 무릎 손상 방지 위해 ATG(<75)는 카운트로만."""
    return RepCounter(down_th=down_th, up_th=up_th, name="squat", min_dwell_ms=min_dwell_ms)


def PushupCounter(down_th: float = 90.0, up_th: float = 160.0,
                  min_dwell_ms: float = 200.0) -> RepCounter:
    """팔꿈치 각도 shoulder-elbow-wrist 기반.
    down<90 → 내려감 (가슴이 바닥 근처), up>160 → 펴짐 (팔꿈치 lockout 직전)."""
    return RepCounter(down_th=down_th, up_th=up_th, name="pushup", min_dwell_ms=min_dwell_ms)
