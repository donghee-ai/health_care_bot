"""관절 각도 + 자세 분류.

함정 방지:
  - keypoint conf 임계 미달이면 None 반환 (NaN 전파 차단)
  - 정의역 안전 - np.clip(cos, -1, 1)로 acos 도메인 보호
  - 좌/우 선택은 pick_angle() 헬퍼로 통일
"""
import numpy as np

from pose_utils import KP


def angle_3pt(a, b, c):
    """3개 2D 점 (y, x), 중심 b - 각도 0~180 deg."""
    ba = a - b
    bc = c - b
    cos = float(np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-9))
    return float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))


def _joint_angle(kp, names, conf_th):
    a_i, b_i, c_i = (KP[n] for n in names)
    if min(kp[a_i, 2], kp[b_i, 2], kp[c_i, 2]) < conf_th:
        return None
    return angle_3pt(kp[a_i, :2], kp[b_i, :2], kp[c_i, :2])


def knee_angle(kp, side, conf_th=0.3):
    """hip-knee-ankle 각도. side='left'|'right'."""
    return _joint_angle(kp, (f"{side}_hip", f"{side}_knee", f"{side}_ankle"), conf_th)


def elbow_angle(kp, side, conf_th=0.3):
    """shoulder-elbow-wrist 각도. side='left'|'right'."""
    return _joint_angle(kp, (f"{side}_shoulder", f"{side}_elbow", f"{side}_wrist"), conf_th)


def shoulder_elev_angle(kp, side, conf_th=0.3):
    """elbow-shoulder-hip 각도 = 어깨 올림(팔 들기) 각도. side='left'|'right'.

    팔을 내리면 ≈10~20°, 옆으로 어깨 높이(레터럴 레이즈)면 ≈90°,
    머리 위로 편 상태(숄더프레스)면 ≈160~170°. 정면을 보고 서서 하는
    상체 운동을 하나의 각도로 커버한다 (몸 방향 무관, 이미지 평면 안 움직임)."""
    return _joint_angle(kp, (f"{side}_elbow", f"{side}_shoulder", f"{side}_hip"), conf_th)


def pick_angle(left, right, mode="better"):
    """좌/우 중 1개 대표 각도.
    'better': 둘 다 있으면 평균, 한쪽만 있으면 그쪽.
    'left'/'right': 강제 선택. 'avg': 둘 다 있을 때만 평균.
    """
    if mode == "left":
        return left
    if mode == "right":
        return right
    if mode == "avg":
        return (left + right) / 2.0 if (left is not None and right is not None) else None
    if left is not None and right is not None:
        return (left + right) / 2.0
    return left if left is not None else right


def body_orientation(kp, conf_th=0.3):
    """어깨중점-엉덩이중점 라인의 수직성으로 자세 분류.
       returns 'vertical' (서있음 → squat) | 'horizontal' (엎드림 → pushup) | None.

    pushup 자세에서 어깨↔엉덩이 라인은 수평에 가까움 (|dy| < |dx|).
    squat 자세에서는 수직 (|dy| > |dx|).
    """
    ls, rs = KP["left_shoulder"], KP["right_shoulder"]
    lh, rh = KP["left_hip"], KP["right_hip"]
    confs = [kp[ls, 2], kp[rs, 2], kp[lh, 2], kp[rh, 2]]
    if min(confs) < conf_th:
        return None
    shoulder = (kp[ls, :2] + kp[rs, :2]) / 2.0
    hip = (kp[lh, :2] + kp[rh, :2]) / 2.0
    dy = abs(shoulder[0] - hip[0])
    dx = abs(shoulder[1] - hip[1])
    return "horizontal" if dx > dy else "vertical"
