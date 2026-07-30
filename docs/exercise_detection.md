# 운동 인식·카운팅 설계 (Exercise Detection)

스쿼트 / 숄더프레스 / 레터럴레이즈가 **어떻게 감지·카운트되는지**와, 종목별
PTZ 추적이 왜 달라지는지 정리한 설계 문서. 실제 코드는 `src/`에 있고 각 절에
파일·함수를 표기했다.

---

## 1. 큰 그림

```
카메라 프레임
  └─ MoveNet Thunder INT8 (TFLite)  → 17개 keypoint (x, y, confidence)
       ├─ 관절 각도 계산            (src/angles.py)
       │     · 스쿼트   : 무릎 각도 (hip-knee-ankle)
       │     · 숄더/레터럴: 어깨 올림 각도 (elbow-shoulder-hip)
       ├─ RepCounter                (src/exercise_counter.py)  각도 시계열 → rep 수
       └─ PTZ 추적                  (src/ptz_controller.py)    종목별 상체/하체 프레이밍
```

**핵심 전제 — 2D 포즈는 "이미지 평면 안의 각도"만 정확하다.** 관절이 카메라
앞뒤(depth) 방향으로 움직이면 그 각도는 뭉개진다. 그래서 이 봇의 종목은 전부
**정면을 보고 서서, 팔·다리가 화면 평면 안에서 움직이는** 것으로 골랐다.
(푸시업을 뺀 이유 → §7)

---

## 2. 공통 엔진: RepCounter (각도 → rep)  · `src/exercise_counter.py`

모든 종목은 **각도 시계열 하나**를 같은 상태기계에 넣어 rep을 센다. 종목마다
"어떤 각도"와 "임계값"만 다르다.

```
상태: UP  ↔  DOWN
  UP  → (각도 < down_th, 그리고 dwell 경과)  → DOWN
  DOWN → (각도 > up_th,  그리고 dwell 경과)  → UP  ← 이 순간 reps += 1
```

- **히스테리시스** (`down_th < up_th`): 임계값을 하나로 두면 그 근처에서 각도가
  미세 진동할 때 카운트가 폭발한다. 내려가는 문턱과 올라오는 문턱을 벌려 막는다.
- **dwell** (`min_dwell_ms=200`): 상태 전환 후 최소 유지 시간. keypoint 지터로
  인한 순간 떨림을 무시한다.
- 부수 기록: 이번/최고 bottom 각도(`deepest_overall`, `last_rep_min_angle`) —
  자세 피드백·결과 화면용.

좌/우 각도는 `pick_angle(left, right, mode="better")` = **둘 다 보이면 평균,
한쪽만 보이면 그쪽** (`src/angles.py`).

---

## 3. 종목별 상세

### 3.1 스쿼트 (하체)

| 항목 | 값 |
|---|---|
| 각도 | **무릎** = hip-knee-ankle (`angles.py::knee_angle`) |
| 임계 | `down<100°` (앉음) / `up>140°` (일어섬) |
| rep 1회 | 서있음(UP) → 앉음(DOWN) → 일어섬(UP) — **일어설 때 +1** |
| 각도 감각 | 선 자세 ≈170°, 무릎 90° 스쿼트 ≈90° |

무릎은 3점(엉덩이·무릎·발목)이 다 보여야 각도가 나온다 → **발목까지 프레임에
들어오는 거리**에서 해야 카운트된다.

### 3.2 숄더프레스 / 팔 위로 올리기 (상체)

| 항목 | 값 |
|---|---|
| 각도 | **어깨 올림** = elbow-shoulder-hip (`angles.py::shoulder_elev_angle`) |
| 임계 | `down<60°` (팔 내림) / `up>140°` (머리 위로 편 상태) |
| rep 1회 | 팔 내림(DOWN) → 팔 올림(UP) — **올릴 때 +1**, 내리면 다음 rep 준비 |
| 각도 감각 | 팔 내림 ≈15°, 머리 위로 곧게 ≈165° |

### 3.3 사이드 레터럴 레이즈 (상체)

| 항목 | 값 |
|---|---|
| 각도 | **같은 어깨 올림 각도** (elbow-shoulder-hip) |
| 임계 | `down<35°` (팔 내림) / `up>80°` (어깨 높이 수평) |
| rep 1회 | 팔 내림 → 옆으로 어깨 높이 — **올릴 때 +1** |
| 각도 감각 | 옆으로 수평 ≈90° |

> 팔꿈치를 **곧게 편 상태**여야 각도가 깔끔하다. 굽히면 팔꿈치가 몸통 쪽으로
> 와 elbow-shoulder-hip 각이 왜곡될 수 있다.

---

## 4. 왜 각도 "하나"로 상체 두 종목을 다 세나

`elbow-shoulder-hip`(어깨를 중심으로 한 위팔–몸통 각도) 하나가 팔 높이를 전부 구분한다:

```
팔 내림 ─────────── ≈10~20°
옆으로 수평(레터럴) ─ ≈90°
머리 위로(프레스) ─── ≈160~170°
```

그래서 **각도는 공유하고 임계값만 다르게** 준다:
- 숄더프레스: `up>140` (머리 위까지 가야 1회)
- 레터럴:     `up>80`  (어깨 높이까지만 가면 1회)

`RepCounter` 상태 의미는 스쿼트와 반대다: 상체 종목은 **팔 내림 = DOWN(휴식),
팔 올림 = UP**. rep은 "올리는 순간" 잡히고, 내려야 다음 rep이 준비된다.
결국 **한 번 올렸다 내리면 1회**로 정확히 센다.

---

## 5. 종목 선택 — 자동분류 없음, 웹에서 선택  · `src/main.py::select_counter`

과거엔 몸 방향(세로=스쿼트/가로=푸시업)으로 **자동 분류**했지만, 지금 세 종목은
**전부 정면·직립**이라 방향으로 구분이 안 된다. 그래서:

- 종목은 **웹 UI에서 사용자가 직접 선택** → `POST /api/mode` → `app_state`에 저장.
- 추론 루프는 매 프레임 `app_state.get_mode()`를 읽어 해당 카운터를 쓴다.
- 세 카운터(squat/overhead/lateral)는 **항상 동시에 살아 있어** 모드를 바꿔도
  각자 상태·횟수가 유지된다.

---

## 6. PTZ 추적 — 종목별 상체/하체 프레이밍  · `src/ptz_controller.py`

카메라가 사람을 따라가는 **목표점과 프레이밍이 종목에 따라 달라진다.** 매 프레임
`main.py`가 `ptz.set_track_mode(exercise)`로 넘긴다.

| 모드 | 추적 목표점(`_target`) | pitch 기준 | 데드존 | 이유 |
|---|---|---|---|---|
| **lower (스쿼트)** | 무릎 중점 → 엉덩이 → 몸통 | `0.62` | `0.20` (넓게) | 다리를 프레임에. 스쿼트 상하 바운스를 넓은 데드존으로 무시 |
| **upper (숄더/레터럴)** | **어깨 중점** → 엉덩이 → 몸통 | `0.64` | `0.15` (좁게) | **머리 위로 든 팔이 안 잘리게** 어깨를 화면 하단쪽에 둠. 어깨는 상하로 안 흔들려 좁은 데드존 OK |

- 무릎을 계속 추적하면 상체 운동 때 **머리 위 팔이 프레임 밖으로 잘린다** → 그래서
  상체 모드는 어깨를 추적하고, `pitch_target_y_upper`로 어깨를 화면 아래쪽에 둬
  위쪽에 팔 공간을 남긴다.
- 상체 모드에서는 양무릎 속도배율·무릎 밴드 판정도 자동 제외된다.
- yaw(좌우) 추적·손실 복구(관성) 로직은 두 모드 공통.

---

## 7. 왜 푸시업을 뺐나

2D 포즈에 부적합해서다:
- 정면/사선 푸시업은 **팔이 카메라 앞뒤(depth)로 굽어** 팔꿈치 각도가 뭉개진다.
- 옛 자동분류(가로=푸시업)가 사선/정면 자세를 오분류한다.
- 정직하게 하려면 **옆모습(side view) 고정 세팅**이 필요한데 데모에선 각도 통제가
  어렵다. → 정면·직립 종목(숄더프레스/레터럴)으로 대체.

---

## 8. 튜닝 지점 (실측으로 조정)

임계값은 **합리적 기본값**이다. 스쿼트가 그랬듯 실제 사람으로 맞춰야 한다.

| 무엇 | 어디 | 증상 → 조정 |
|---|---|---|
| 각 종목 up/down 임계 | `main.py` `--*-th` 플래그 / `exercise_counter.py` 기본값 | rep 누락 → 임계 간격을 좁힘 / 중복 → 넓힘·dwell↑ |
| 상체 프레이밍 | `ptz_controller.py::pitch_target_y_upper` (0.64) | 머리 위 팔이 잘림 → **0.68~0.72로 키움**(어깨를 더 아래로) |
| 레터럴 좌우 잘림 | (코드 아님) | 줌이 없음 → **사람이 더 뒤로** |
| conf 임계 | `--conf` (0.3) | keypoint 불안정 → 올림 |

---

## 9. 파일 지도

```
src/angles.py            knee_angle, shoulder_elev_angle, pick_angle
src/exercise_counter.py  RepCounter + SquatCounter/OverheadPressCounter/LateralRaiseCounter
src/main.py              select_counter, compute_angle, 루프에서 카운터·PTZ 구동
src/ptz_controller.py    _target, set_track_mode, update (상체/하체 프레이밍)
src/pose_utils.py        knee/hip/shoulder_center_normalized, keypoint 상수
src/app_state.py         모드(mode) + 세션 상태
```

## 관련 히스토리
- [`history/2026-07-26_02`](history/2026-07-26_02_pushup_removed_overhead_lateral_added.md) — 푸시업 제거·상체 종목 추가
- [`history/2026-07-26_03`](history/2026-07-26_03_ptz_track_mode_upper_lower_body.md) — PTZ 상체/하체 추적
