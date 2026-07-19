"""수동 검증용 목업 서버 — 카메라/모델 없이 http_server.py + app_state.py 통합 확인.
실제 배포에는 쓰이지 않음. `python scripts/mock_serve.py` 후 web/ 에서
`VITE_BACKEND_URL=http://localhost:8090 npm run dev` 로 프론트 확인.
"""
import sys
import time
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import cv2
import numpy as np

import app_state
from http_server import update_live_state, start_server, init_app
from ptz_controller import PTZController
from exercise_counter import SquatCounter, PushupCounter


def main():
    ptz = PTZController()
    ptz.open()
    squat_c = SquatCounter()
    pushup_c = PushupCounter()
    app_state.set_mode("auto")

    init_app(ptz=ptz, squat_c=squat_c, pushup_c=pushup_c, avg_fps_fn=lambda: 27.4)
    start_server(8090)
    print("mock server on http://localhost:8090 (/app, /stats.json, /stream.mjpg)")

    frame_idx = 0
    while True:
        img = np.full((480, 640, 3), 40, dtype=np.uint8)
        cv2.putText(img, f"MOCK FRAME {frame_idx}", (40, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
        live = {
            "frame": frame_idx,
            "fps": 27.4,
            "loop_ms": 36.5,
            "mode": app_state.get_mode(),
            "exercise_active": "squat",
            "orientation": "vertical",
            "angle_deg": {"left": 92.0, "right": 94.0, "used": 93.0},
            "person_center_norm": [0.5, 0.5],
            "squat": squat_c.snapshot(),
            "pushup": pushup_c.snapshot(),
            "last_ptz_cmd": None,
            "dropped_frames": 0,
            "rss_mb": 210.5,
            "cpu_temp_c": 52.3,
        }
        update_live_state(img, live, q=70)
        frame_idx += 1
        time.sleep(0.1)


if __name__ == "__main__":
    main()
