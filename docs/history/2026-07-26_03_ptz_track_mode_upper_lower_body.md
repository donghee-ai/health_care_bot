# 2026-07-26 — PTZ 추적을 종목별 상체/하체로 분리

## 시점

2026-07-26. [`2026-07-26_02`](2026-07-26_02_pushup_removed_overhead_lateral_added.md)에서
숄더프레스·레터럴을 추가한 직후. 사용자 지적: "모드별로 추적이 달라져야 한다 —
상반신/하반신."

## 왜

PTZ 컨트롤러가 **항상 무릎 우선**(무릎중점→엉덩이→몸통)으로 추적하고
`pitch_target_y=0.62`(무릎을 화면 하단)로 프레이밍한다. 스쿼트엔 맞지만
**상체 운동(숄더프레스/레터럴)은 팔이 머리 위로 올라가므로 무릎을 추적하면
머리 위 팔이 프레임 밖으로 잘린다.** 종목에 따라 추적 타깃·프레이밍을 바꿔야 한다.

## 무엇을

`PTZController`에 `track_mode`("lower"|"upper")를 추가하고, main.py가 매 프레임
운동 종목에 맞춰 `set_track_mode(exercise)`로 넘긴다.

- **lower (스쿼트)**: 무릎 중점 추적, `pitch_target_y=0.62`, 넓은 데드존(0.20).
  기존과 100% 동일 (track_mode 기본값 "lower").
- **upper (overhead/lateral)**: **어깨 중점 추적**, `pitch_target_y_upper=0.64`
  (어깨를 화면 하단쪽에 둬 **머리 위 든 팔 공간 확보**), 좁은 데드존(0.15,
  어깨는 상하로 거의 안 흔들림). 무릎 밴드 판정·양무릎 속도배율은 하체 모드에서만.

## 구현 (파일별)

- `src/pose_utils.py`: `shoulder_center_normalized()` 추가 (`_mean_center` 재사용).
- `src/ptz_controller.py`:
  - 필드 `pitch_target_y_upper=0.64`, `pitch_deadzone_upper=0.15`, `track_mode="lower"`.
  - `set_track_mode(exercise_or_mode)`: overhead/lateral/'upper' → "upper", 그 외 "lower".
  - `_target()`: upper면 어깨중점→엉덩이→몸통, lower면 무릎중점→엉덩이→몸통.
  - `update()`: 모드별 `pt_y`/`pdz` 적용, `both_knees`는 lower 모드에서만 계산
    (upper면 양무릎 속도배율·무릎밴드 판정 자동 제외).
- `src/main.py`: `ptz.update()` 직전에 `ptz.set_track_mode(exercise)` 호출.

## 검증

- 컨테이너 정상 기동(fps ~11, camera video2), 크래시 없음.
- `/api/mode` 전환 시 `exercise_active` 즉시 추종 확인.
- **주의**: 무인 상태 자동 테스트에선 `ptz.target_norm`이 세 모드 모두 비슷하게
  나왔다 — 사람이 없으면 `_target`이 None이라 추적점이 갱신되지 않기 때문.
  **상체/하체 프레이밍 차이는 실제 사람이 서야 검증된다.**

## 남은 것 (실제 측정 필요)

- 사람이 서서 **숄더프레스/레터럴 시 머리 위 팔이 프레임 안에 남는지** 확인.
  잘리면 `pitch_target_y_upper`를 키워(예: 0.68~0.72) 어깨를 더 아래로 내린다.
- 레터럴은 팔이 옆으로 넓게 벌어져 **좌우 프레임에 걸릴 수 있음**(줌 없음) —
  사람이 충분히 뒤에 서야 함. 코드로는 해결 불가, 세팅으로 대응.
- 스쿼트 동작이 종전과 동일한지 회귀 확인.

## 관련

- 실행: `cd ~/health_care_bot && bash docker/run.sh` → `http://192.168.0.45:8080/app`
- 이전: [`2026-07-26_02`](2026-07-26_02_pushup_removed_overhead_lateral_added.md)
