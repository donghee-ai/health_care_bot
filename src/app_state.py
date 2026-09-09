"""앱(모바일 웹) 계층 상태 - 세션 관리 + 운영자 제어권 lock.

추론 루프(main.py)와 무관하게 동작하는 순수 상태 객체.
http_server.py의 API handler가 이 모듈의 함수를 호출해 상태를 읽고 쓴다.
스레드 안전을 위해 모든 접근은 전역 lock 하나로 직렬화한다 (호출 빈도가
낮아 - 사람이 누르는 버튼 수준 - lock contention은 문제되지 않음).
"""
import os
import threading
import time
import uuid

_lock = threading.Lock()

# === 운영자 제어권 lock ===
# PIN은 데모 중 오조작 방지용이지 인증이 아니다 (docs/02 §6 보안 모델).
# 공개 리포에 기본값이 박혀 있으므로 시연 전에는 HCB_OPERATOR_PIN으로 바꿀 것.
# docker/run.sh가 이 환경변수를 컨테이너로 전달한다.
_DEFAULT_OPERATOR_PIN = "1234"
_operator_pin = os.environ.get("HCB_OPERATOR_PIN", "").strip() or _DEFAULT_OPERATOR_PIN
_control_client_id = None
_control_expires_ms = 0.0
_CONTROL_LOCK_MS = 60_000.0

# === 운동 세션 상태 ===
_session = {
    "session_id": None,
    "mode": "squat",         # squat | overhead | lateral | guard
    "status": "idle",        # idle | running | paused | finished
    "target_reps": 20,
    "started_at_ms": None,
    "paused_elapsed_ms": 0.0,
    "pause_started_ms": None,
    "last_finished": None,   # 마지막 세션 요약 (dict) - 결과 화면용
}

# === 경비 모드 ===
# guard로 전환한 시점부터 GUARD_ARM_DELAY_MS 뒤에 "무장"된다 (전환 순간 사람이
# 화면 안에 있어도 바로 찍히지 않게). 무장 후 사람 감지 시 촬영하되,
# GUARD_CAPTURE_COOLDOWN_MS 안에는 재촬영하지 않는다 (같은 사람이 서있는 동안
# 프레임마다 저장하는 것 방지).
GUARD_ARM_DELAY_MS = 5_000.0
GUARD_CAPTURE_COOLDOWN_MS = 5_000.0
_guard = {
    "armed_at_ms": None,     # 이 시각 이후로 무장 (None = 비무장/비활성)
    "last_capture_ms": None,
    "capture_count": 0,
    "force_capture": False,  # 웹 "직접 촬영" 버튼 - 무장/사람감지 여부와 무관하게 즉시 촬영
}


def _now_ms():
    return time.time() * 1000.0


# ---------- 운영자 제어권 ----------

def claim_control(client_id: str, pin: str) -> dict:
    global _control_client_id, _control_expires_ms
    with _lock:
        if pin != _operator_pin:
            return {"ok": False, "error": "invalid_pin"}
        now = _now_ms()
        if (_control_client_id is not None and _control_client_id != client_id
                and _control_expires_ms > now):
            return {
                "ok": False,
                "error": "locked_by_other",
                "locked_by": _control_client_id,
            }
        _control_client_id = client_id
        _control_expires_ms = now + _CONTROL_LOCK_MS
        return {"ok": True, "lock_until_ms": int(_control_expires_ms)}


def heartbeat_control(client_id: str) -> dict:
    global _control_expires_ms
    with _lock:
        now = _now_ms()
        if _control_client_id != client_id or _control_expires_ms <= now:
            return {"ok": False, "error": "not_holder"}
        _control_expires_ms = now + _CONTROL_LOCK_MS
        return {"ok": True, "lock_until_ms": int(_control_expires_ms)}


def release_control(client_id: str) -> dict:
    global _control_client_id, _control_expires_ms
    with _lock:
        if _control_client_id == client_id:
            _control_client_id = None
            _control_expires_ms = 0.0
        return {"ok": True}


def has_control(client_id: str) -> bool:
    with _lock:
        return _control_client_id == client_id and _control_expires_ms > _now_ms()


def control_snapshot() -> dict:
    with _lock:
        now = _now_ms()
        active = _control_client_id is not None and _control_expires_ms > now
        return {
            "locked": active,
            "locked_by": _control_client_id if active else None,
            "lock_remaining_ms": max(0, int(_control_expires_ms - now)) if active else 0,
        }


# ---------- 운동 세션 ----------

def set_mode(mode: str) -> dict:
    if mode not in ("squat", "overhead", "lateral", "guard"):
        return {"ok": False, "error": "invalid_mode"}
    with _lock:
        was_guard = _session["mode"] == "guard"
        _session["mode"] = mode
        if mode == "guard" and not was_guard:
            _guard["armed_at_ms"] = _now_ms() + GUARD_ARM_DELAY_MS
        elif mode != "guard":
            _guard["armed_at_ms"] = None
        return {"ok": True, "mode": mode}


def get_mode() -> str:
    with _lock:
        return _session["mode"]


# ---------- 경비 모드 ----------

def guard_is_armed() -> bool:
    """guard 모드이고 무장 딜레이가 지났으면 True."""
    with _lock:
        armed_at = _guard["armed_at_ms"]
        return armed_at is not None and _now_ms() >= armed_at


def guard_try_capture() -> bool:
    """쿨다운을 통과했으면 촬영을 "예약"(카운트+마지막 시각 갱신)하고 True 반환.
    실제 이미지 저장은 호출부(main.py)가 True를 받은 뒤 수행한다."""
    with _lock:
        now = _now_ms()
        last = _guard["last_capture_ms"]
        if last is not None and now - last < GUARD_CAPTURE_COOLDOWN_MS:
            return False
        _guard["last_capture_ms"] = now
        _guard["capture_count"] += 1
        return True


def guard_request_capture() -> dict:
    """웹 "직접 촬영" 버튼 - 무장 상태·사람 감지와 무관하게 다음 프레임에서
    즉시 촬영하도록 요청한다."""
    with _lock:
        _guard["force_capture"] = True
    return {"ok": True}


def guard_register_manual_capture():
    """수동 촬영은 자동 감지 쿨다운(GUARD_CAPTURE_COOLDOWN_MS)을 무시하고 무조건
    즉시 찍혀야 한다 - 안 그러면 사람이 계속 화면 안에 있어(테스트 중 본인처럼)
    자동 촬영이 쿨다운을 계속 선점할 때 버튼을 눌러도 조용히 씹혀서 "안 되는
    것"처럼 보인다. 카운트/마지막 촬영 시각은 갱신해 이후 자동 감지 쿨다운
    계산에는 그대로 반영되게 한다(수동 찍은 직후 자동이 또 바로 찍히진 않음)."""
    with _lock:
        _guard["last_capture_ms"] = _now_ms()
        _guard["capture_count"] += 1


def guard_pop_force_capture() -> bool:
    """main.py가 매 프레임 호출 - 요청이 있었으면 True를 반환하고 플래그를 소비(리셋)한다."""
    with _lock:
        v = _guard["force_capture"]
        _guard["force_capture"] = False
        return v


def guard_snapshot() -> dict:
    with _lock:
        armed_at = _guard["armed_at_ms"]
        now = _now_ms()
        armed = armed_at is not None and now >= armed_at
        arm_remaining_ms = max(0, round(armed_at - now)) if (armed_at is not None and not armed) else 0
        return {
            "active": _session["mode"] == "guard",
            "armed": armed,
            "arm_remaining_ms": arm_remaining_ms,
            "capture_count": _guard["capture_count"],
            "last_capture_ms": _guard["last_capture_ms"],
        }


def session_start(target_reps: int = None) -> dict:
    with _lock:
        _session["session_id"] = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
        _session["status"] = "running"
        _session["started_at_ms"] = _now_ms()
        _session["paused_elapsed_ms"] = 0.0
        _session["pause_started_ms"] = None
        if target_reps is not None:
            _session["target_reps"] = max(1, int(target_reps))
        return {"ok": True, "session": dict(_session)}


def session_pause() -> dict:
    with _lock:
        if _session["status"] != "running":
            return {"ok": False, "error": "not_running"}
        _session["status"] = "paused"
        _session["pause_started_ms"] = _now_ms()
        return {"ok": True, "session": dict(_session)}


def session_resume() -> dict:
    with _lock:
        if _session["status"] != "paused":
            return {"ok": False, "error": "not_paused"}
        if _session["pause_started_ms"] is not None:
            _session["paused_elapsed_ms"] += _now_ms() - _session["pause_started_ms"]
            _session["pause_started_ms"] = None
        _session["status"] = "running"
        return {"ok": True, "session": dict(_session)}


def session_reset(reset_counters_fn=None) -> dict:
    with _lock:
        _session["status"] = "idle"
        _session["started_at_ms"] = None
        _session["paused_elapsed_ms"] = 0.0
        _session["pause_started_ms"] = None
        _session["last_finished"] = None
    if reset_counters_fn is not None:
        reset_counters_fn()
    return {"ok": True}


def session_finish(snaps=None, avg_fps=None) -> dict:
    """snaps = {"squat": snapshot, "overhead": ..., "lateral": ...} (일부 None 허용)."""
    snaps = snaps or {}
    with _lock:
        if _session["started_at_ms"] is None:
            return {"ok": False, "error": "no_active_session"}
        elapsed_ms = _now_ms() - _session["started_at_ms"] - _session["paused_elapsed_ms"]
        if _session["status"] == "paused" and _session["pause_started_ms"] is not None:
            elapsed_ms -= (_now_ms() - _session["pause_started_ms"])
        summary = {
            "session_id": _session["session_id"],
            "mode": _session["mode"],
            "elapsed_ms": max(0, round(elapsed_ms)),
            "reps": {k: (v or {}).get("reps", 0) for k, v in snaps.items()},
            "best_deg": {k: (v or {}).get("deepest_overall_deg") for k, v in snaps.items()},
            "avg_fps": avg_fps,
            "finished_at_ms": int(_now_ms()),
        }
        _session["status"] = "finished"
        _session["last_finished"] = summary
        return {"ok": True, "summary": summary}


def session_elapsed_ms() -> float:
    with _lock:
        if _session["started_at_ms"] is None:
            return 0.0
        elapsed = _now_ms() - _session["started_at_ms"] - _session["paused_elapsed_ms"]
        if _session["status"] == "paused" and _session["pause_started_ms"] is not None:
            elapsed -= (_now_ms() - _session["pause_started_ms"])
        return max(0.0, elapsed)


def session_snapshot() -> dict:
    with _lock:
        s = dict(_session)
    s["elapsed_ms"] = round(session_elapsed_ms())
    return s
