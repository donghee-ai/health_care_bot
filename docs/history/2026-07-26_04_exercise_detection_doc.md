# 2026-07-26 — 운동 인식·카운팅 설계 문서 작성

## 시점

2026-07-26. 종목 개편([`_02`](2026-07-26_02_pushup_removed_overhead_lateral_added.md))과
PTZ 상체/하체 추적([`_03`](2026-07-26_03_ptz_track_mode_upper_lower_body.md))을 마친 뒤,
"스쿼트·숄더프레스가 어떻게 동작하는지" 정식 문서화 요청.

## 무엇을

[`docs/exercise_detection.md`](../exercise_detection.md) 신규 작성 — 운동 감지·카운팅의
**설계 레퍼런스**. 히스토리(경위)와 달리 "지금 어떻게 동작하는가"를 정리한 문서다.

담은 내용:
- 큰 그림(카메라→MoveNet 17kp→각도→RepCounter→PTZ)과 2D 포즈 전제.
- 공통 엔진 `RepCounter`: UP↔DOWN 상태기계 + 히스테리시스 + dwell.
- 종목별 각도·임계·rep 정의:
  - 스쿼트 = 무릎(hip-knee-ankle), down<100/up>140.
  - 숄더프레스 = 어깨올림(elbow-shoulder-hip), down<60/up>140.
  - 레터럴 = 같은 각도, down<35/up>80.
- 왜 각도 하나로 상체 두 종목을 다 세는지(팔 내림10°/수평90°/머리위165°).
- 모드 선택(자동분류 없음, 웹에서 /api/mode).
- PTZ 상체/하체 추적 표.
- 왜 푸시업을 뺐나(2D depth 문제).
- 튜닝 지점 표 + 파일 지도.

## 관련

- 문서: [`docs/exercise_detection.md`](../exercise_detection.md)
- 구현 히스토리: [`_02`](2026-07-26_02_pushup_removed_overhead_lateral_added.md),
  [`_03`](2026-07-26_03_ptz_track_mode_upper_lower_body.md)
