"""경비 모드 - 사람 감지 시 프레임 저장 + 로그 기록.

app_state가 무장/쿨다운 판정을 갖고 있고, 이 모듈은 순수하게
(1) keypoint로 사람 존재를 판정하고 (2) 저장 파일명/로그 라인을 만든다.
저장 위치는 리포 밖 개념(런타임 산출물)이라 captures/는 .gitignore 대상이다.
"""
import json
import time
from pathlib import Path

import cv2

from pose_utils import KP

CAPTURE_DIR = Path(__file__).resolve().parent.parent / "captures"
LOG_PATH = CAPTURE_DIR / "guard_log.jsonl"

# 사람 존재 판정에 쓰는 keypoint - 몸통 중심부라 팔다리보다 안정적으로 잡힌다.
_CORE_KP = ("left_shoulder", "right_shoulder", "left_hip", "right_hip")


def person_detected(kp, conf_th: float = 0.3, min_hits: int = 2) -> bool:
    """core keypoint 중 min_hits개 이상이 conf_th를 넘으면 사람 있음으로 판정."""
    hits = sum(1 for n in _CORE_KP if kp[KP[n], 2] >= conf_th)
    return hits >= min_hits


def save_capture(frame_bgr, wall_ms: float, meta: dict = None) -> dict:
    """frame_bgr을 JPEG로 저장하고 로그(JSONL)에 한 줄 append. 저장된 레코드 반환."""
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    t = time.localtime(wall_ms / 1000.0)
    stamp = time.strftime("%Y%m%d_%H%M%S", t)
    ms_part = int(wall_ms % 1000)
    filename = f"guard_{stamp}_{ms_part:03d}.jpg"
    cv2.imwrite(str(CAPTURE_DIR / filename), frame_bgr)

    record = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S", t),
        "ts_ms": int(wall_ms),
        "file": filename,
    }
    if meta:
        record.update(meta)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record
