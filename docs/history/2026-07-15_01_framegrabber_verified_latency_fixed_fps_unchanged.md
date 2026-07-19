# 2026-07-15 — FrameGrabber 배포 검증: 지연 개선 확인, FPS는 예상대로 그대로

## 시점

2026-07-15

## 사건

`docs/history/2026-07-11_05_pd_hub_confirmed_defective_refund.md`에서
예고했던 `FrameGrabber`(캡처 전용 스레드) 수정을 디바이스에 배포하고
실사용으로 검증했다. 사용자 체감: "카메라의 실시간성이 있다"(지연이
확실히 줄어듦). `/stats.json`의 `fps` 값은 **10.8 ±4로 수정 전과 동일** —
이는 결함이 아니라 설계상 당연한 결과임을 확인.

## 배경

`FrameGrabber`는 **지연(latency)**과 **처리량(FPS/throughput)**을 구분해서
봐야 하는 수정이었다.

- 고치기 전: 카메라 캡처(예: ~33ms/frame)가 추론 루프(예: ~90ms/frame)보다
  빨라서, 처리 안 된 프레임이 드라이버 버퍼에 쌓이고 그 오래된 프레임을
  순서대로 소비 — 지연이 계속 누적됨.
- 고친 후: 캡처 스레드가 항상 최신 프레임 1장만 유지하고, 추론 루프는
  그 최신 프레임만 가져다 씀 — 지연이 "루프 1회분"으로 고정됨(더 이상
  누적 안 됨).
- **FrameGrabber는 추론 자체를 빠르게 만들지 않는다.** MoveNet 추론 +
  pose draw + JPEG 인코딩이 여전히 루프당 ~90ms 걸리면, 초당 처리되는
  distinct 프레임 수(=FPS)는 그대로 ~11fps 근처다. 사용자가 체감한
  "실시간성"은 지연이 사라진 것이지, 프레임이 더 자주 갱신되는 게
  아니다.

## 결과

FPS(10.8±4) 수치가 수정 전후로 동일하게 나온 것 자체가 **FrameGrabber가
의도대로 지연만 고치고 처리량은 건드리지 않았다는 증거** — 회귀나 버그가
아님. `web/ARCHITECTURE.md`에 이 지연 vs FPS 구분을 설계 노트로 남김.
원래 버그(버퍼 누적 원인)의 증상/원인/재발방지는
[`docs/issues/2026-07-11_04_camera_buffer_accumulation_causes_growing_latency.md`](../issues/2026-07-11_04_camera_buffer_accumulation_causes_growing_latency.md)
참고.

## 다음 단계

FPS(처리량) 자체를 올리고 싶다면 별도 작업 필요 — 해상도 축소, 추론
스레드/딜리게이트 튜닝, 또는 인코딩 품질 조정 등. 지금은 요구사항 밖이라
미착수.
