"""앱(모바일 웹) 계층 상태 — 세션 관리 + 운영자 제어권 lock.

추론 루프(main.py)와 무관하게 동작하는 순수 상태 객체.
http_server.py의 API handler가 이 모듈의 함수를 호출해 상태를 읽고 쓴다.
스레드 안전을 위해 모든 접근은 전역 lock 하나로 직렬화한다 (호출 빈도가
낮아 — 사람이 누르는 버튼 수준 — lock contention은 문제되지 않음).
"""
import threading
import time
import uuid

_lock = threading.Lock()

# === 운영자 제어권 lock ===
_operator_pin = "1234"
_control_client_id = None
_control_expires_ms = 0.0
_CONTROL_LOCK_MS = 60_000.0

# === 운동 세션 상태 ===
_session = {
    "session_id": None,
    "mode": "auto",          # auto | squat | pushup
    "status": "idle",        # idle | running | paused | finished
    "target_reps": 20,
    "started_at_ms": None,
    "paused_elapsed_ms": 0.0,
    "pause_started_ms": None,
    "last_finished": None,   # 마지막 세션 요약 (dict) — 결과 화면용
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
    if mode not in ("auto", "squat", "pushup"):
        return {"ok": False, "error": "invalid_mode"}
    with _lock:
        _session["mode"] = mode
        return {"ok": True, "mode": mode}


def get_mode() -> str:
    with _lock:
        return _session["mode"]


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


def session_finish(squat_snapshot=None, pushup_snapshot=None, avg_fps=None) -> dict:
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
            "squat_reps": (squat_snapshot or {}).get("reps", 0),
            "pushup_reps": (pushup_snapshot or {}).get("reps", 0),
            "squat_best_deg": (squat_snapshot or {}).get("deepest_overall_deg"),
            "pushup_best_deg": (pushup_snapshot or {}).get("deepest_overall_deg"),
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
