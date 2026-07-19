"""MoveNet 17 keypoint 상수 + letterbox 전후처리 + draw helpers.

기존 pose/scripts/infer_camera_pose.py에서 재사용 — 본 라인은
헬스케어 봇 통합 (squat + pushup + ptz) 용도로만 추출.
"""
import cv2
import numpy as np


KP_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]
KP = {n: i for i, n in enumerate(KP_NAMES)}

SKELETON = [
    (5, 7), (7, 9),
    (6, 8), (8, 10),
    (5, 6),
    (5, 11), (6, 12),
    (11, 12),
    (11, 13), (13, 15),
    (12, 14), (14, 16),
    (0, 1), (0, 2), (1, 3), (2, 4),
]


def letterbox_square(image_bgr, target=256, pad_value=114):
    """비율 유지하며 target×target 정사각으로 패딩. pad_value=114 (YOLO 관례)."""
    h, w = image_bgr.shape[:2]
    s = target / max(h, w)
    nh, nw = int(round(h * s)), int(round(w * s))
    resized = cv2.resize(image_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
    pad_t = (target - nh) // 2
    pad_l = (target - nw) // 2
    pad_b = target - nh - pad_t
    pad_r = target - nw - pad_l
    padded = cv2.copyMakeBorder(
        resized, pad_t, pad_b, pad_l, pad_r,
        cv2.BORDER_CONSTANT, value=(pad_value, pad_value, pad_value),
    )
    return padded, (pad_l, pad_t, s)


def unletterbox_kp(kp_norm, pad_info, target=256):
    """MoveNet 출력 [17, (y_norm, x_norm, conf)] → 원본 픽셀 (y, x, conf)."""
    pad_l, pad_t, s = pad_info
    out = kp_norm.copy().astype(np.float32)
    out[:, 0] = (kp_norm[:, 0] * target - pad_t) / s
    out[:, 1] = (kp_norm[:, 1] * target - pad_l) / s
    return out


def person_center_normalized(kp, frame_h, frame_w, conf_th=0.3):
    """어깨/엉덩이 중점 → frame 안 정규화 좌표 (x_norm, y_norm) ∈ [0,1].
    유효 keypoint 없으면 (None, None)."""
    names = ("left_shoulder", "right_shoulder", "left_hip", "right_hip")
    valid = [kp[KP[n], :2] for n in names if kp[KP[n], 2] >= conf_th]
    if not valid:
        return None, None
    yx = np.mean(valid, axis=0)
    return (
        float(np.clip(yx[1] / frame_w, 0.0, 1.0)),
        float(np.clip(yx[0] / frame_h, 0.0, 1.0)),
    )


# 스쿼트 PTZ 추적용 가중치 — 무릎(측정 대상 관절)에 가장 큰 비중을 둬서
# 카메라가 무릎을 화면 안에 우선적으로 유지하도록 함. hip/shoulder는 낮은
# 비중으로 남겨 상반신이 통째로 프레임 밖으로 밀려나는 걸 막는 역할.
SQUAT_TRACK_WEIGHTS = {
    "left_knee": 0.25,
    "right_knee": 0.25,
    "left_hip": 0.15,
    "right_hip": 0.15,
    "left_shoulder": 0.10,
    "right_shoulder": 0.10,
}


def person_center_weighted(kp, frame_h, frame_w, conf_th=0.3, weights=None):
    """keypoint별 가중 평균 기반 추적 중심점. weights: {keypoint_name: weight}.
    confidence가 낮아 빠진 keypoint가 있으면 남은 것들로 가중치를 재정규화
    (즉 무릎이 안 보이면 hip/shoulder만으로 비율 맞춰 계속 추적).
    weights의 keypoint가 전부 안 보이면 (None, None)."""
    if weights is None:
        weights = SQUAT_TRACK_WEIGHTS
    valid = [(kp[KP[n], :2], w) for n, w in weights.items() if kp[KP[n], 2] >= conf_th]
    if not valid:
        return None, None
    total_w = sum(w for _, w in valid)
    yx = np.zeros(2, dtype=np.float32)
    for pt, w in valid:
        yx += pt * (w / total_w)
    return (
        float(np.clip(yx[1] / frame_w, 0.0, 1.0)),
        float(np.clip(yx[0] / frame_h, 0.0, 1.0)),
    )


def draw_pose(image, kp, conf_th=0.3, highlight=None):
    """skeleton + keypoint dot + highlight (옵션: 강조할 keypoint index 목록)."""
    for a, b in SKELETON:
        if kp[a, 2] >= conf_th and kp[b, 2] >= conf_th:
            pa = (int(kp[a, 1]), int(kp[a, 0]))
            pb = (int(kp[b, 1]), int(kp[b, 0]))
            cv2.line(image, pa, pb, (0, 255, 0), 2, cv2.LINE_AA)
    for i in range(17):
        if kp[i, 2] >= conf_th:
            p = (int(kp[i, 1]), int(kp[i, 0]))
            cv2.circle(image, p, 4, (0, 200, 255), -1)
    if highlight:
        for i in highlight:
            if kp[i, 2] >= conf_th:
                p = (int(kp[i, 1]), int(kp[i, 0]))
                cv2.circle(image, p, 8, (0, 0, 255), 2, cv2.LINE_AA)
    return image
