# 2026-07-17 — PTZ 추적 + 스쿼트 카운팅 통합 v2 확정 + 백업

## 시점

2026-07-17 (PTZ 추적 v1
[2026-07-17_03](2026-07-17_03_ptz_camera_tracking_v1_local_pc.md) 이어서)

## 사건

PC 로컬 PTZ 추적 스크립트(`scripts/ptz_camera_track.py`)에 **스쿼트 rep 카운팅**을
붙여 "추적 + 카운팅"이 한 루프에서 동시에 도는 v2를 완성하고 백업했다.

백업: `scripts/ptz_camera_track_v2_ptz_squat.py` (byte-identical)

## 배경

- 카운팅 로직을 새로 짜지 않고 **본 라인의 검증된 모듈을 그대로 재사용**:
  `src/exercise_counter.py::SquatCounter` (UP↔DOWN 히스테리시스 100°↔140°,
  `min_dwell_ms=200` 지터 방지) + `src/angles.py::knee_angle`(hip-knee-ankle) /
  `pick_angle`(좌우 선택). `src/main.py`가 쓰는 것과 동일한 패턴.
- 추적 목표점(무릎 중점)과 카운팅 입력(무릎 각도)이 같은 무릎 키포인트를 쓰므로
  자연스럽게 한 파이프라인에서 처리됨.

## 결과 — v2 추가분 (v1 기능은 그대로 유지)

- 매 프레임 무릎 각도 계산 → `SquatCounter.update(angle, now_ms)` → rep 검출
- 화면 우상단 `SQUAT <n> [UP|DOWN]` + `knee <deg>deg`, rep 완료 순간 노란색 강조
- 콘솔 `★ SQUAT REP #n bottom=<deg>deg (frame N)`, 종료 시 총 reps/deepest 요약
- 키: `q` 종료, **`r` 카운트 리셋**
- 옵션: `--squat-down-th`(100) / `--squat-up-th`(140) / `--min-dwell-ms`(200) /
  `--side {left,right,avg,better}` / `--no-count`(카운팅 끄기)

검증: 합성 각도 시퀀스(하강→상승 2회)로 REP 2회·bottom 85°/80°·deepest 80° 정상
검출 확인. 스크립트 전체 헤드리스 스모크 테스트 통과(크래시 없음).

## 주의 / 실측 조건

- **무릎 각도는 hip·knee·ankle 3점이 모두 conf 임계 이상이어야 계산됨** →
  카운팅하려면 최소 발목까지 프레임에 들어오는 거리에서 촬영해야 함.
- 카메라 인덱스는 USB 재연결 때마다 뒤바뀔 수 있음 (이번에 내장 웹캠↔짐벌
  카메라가 0↔1로 스왑됨). 헷갈리면 각 인덱스에서 한 장 캡처해 확인할 것.
- 같은 시점에 서보가 ID 1~5 전부 무응답인 상태가 발생 → COM 포트/ID 문제가 아니라
  **서보 외부 전원(6~12.6V)·버스 케이블** 쪽 이슈로 좁혀짐(포트는 정상 오픈).

## 다음 단계

- pitch 세로 프레이밍 튜닝(목표 y 0.5 → 0.65~0.7)은 v1부터 이월된 미해결 항목.
- 서보 전원 복구 후 실제 스쿼트로 카운팅 실측 검증(현재는 합성 검증까지만).
- 본 파이프라인(`src/main.py`) 통합 여부는 미결정 — 현재는 독립 테스트 스크립트.
