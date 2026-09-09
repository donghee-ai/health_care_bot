# 하드웨어 현재값 · 캘리브레이션 / 재조립 절차

본 문서는 짐벌·서보의 **현재 확정값**과, 재조립·재배선했을 때 그 값을 다시 세우는 절차를
정리합니다. 여기 적힌 값은 전부 **지금의 물리적 장착 상태에 의존**하므로, 기구부를 건드렸다면
§4를 반드시 거쳐야 합니다.

구현: [`src/st3215_bus.py`](../src/st3215_bus.py) ·
[`scripts/calibrate_st3215.py`](../scripts/calibrate_st3215.py) ·
[`scripts/test_st3215_serial.py`](../scripts/test_st3215_serial.py)

## 0. 한 눈에 — 현재 확정값

| 항목 | 값 | 근거 |
|---|---|---|
| yaw 서보 (좌우) | **ID = 1** (체인 첫 번째) — **베이스에 장착** | 2026-07-16 |
| pitch 서보 (상하) | **ID = 2** (yaw에서 데이지체인) — **헤드에 장착** | 2026-07-16 |
| 중앙 기준 | tick **2047 = 180°** (EEPROM Homing_Offset 캘리브레이션) | 2026-07-17 |
| yaw 가동범위 | **90 ~ 270°** (중앙 ±90) | 2026-07-17 실측 |
| pitch 가동범위 | **150 ~ 210°** (중앙 ±30) | 2026-07-17 실측 |
| pitch 방향 | 현재 장착 상태에서는 **`pitch_sign=-1`이 정상** (2026-08-07 재조립 후 확정) | 2026-08-07 실측 |
| yaw 방향 | 기본값 `yaw_sign=+1`이 정상 | 2026-07-19 실기 |
| 회전 속도 | 569 tick/s ≈ 50 deg/s (옛 PWM 20 ms/° 등가) | 안전상 고정 |
| 버스 | 1,000,000 baud, half-duplex 3선(VCC/GND/DATA) | |
| 포트 | 디바이스 `/dev/ttyACM0` (CH343, CDC-ACM) / PC `COM9` | |

Homing_Offset 실측 이력 (참고 — **최신이 유효**):

| 시점 | yaw(ID=1) | pitch(ID=2) | 비고 |
|---|---|---|---|
| 2026-07-17 | -1117 | -713 | 최초 캘리브레이션 |
| **2026-07-21** | **-492** | **-1341** | 재조립 후 재캘리브레이션 (현재) |

값이 달라진 것은 그새 서보가 다른 물리 자세로 재조립됐기 때문이다 — **오프셋 값 자체를
문서에서 베껴 쓰지 말고, 절차(§4)로 다시 세울 것.**

### 0-1. 두 모터가 어디에 있나

혼동하기 쉬워서 적어둔다 — **모터가 한곳에 모여 있지 않다.**

| | 들어 있는 것 |
|---|---|
| **헤드**(위쪽 육각 통) | 카메라 + **pitch(상하) 서보 ID=2** |
| **기둥** | 두 통을 잇는 축 (pitch 관절이 여기 붙는다) |
| **베이스**(아래쪽 육각 통) | **yaw(좌우) 서보 ID=1** + UNO Q + 셀프파워 허브 + Bus Servo Adapter |

그래서 **yaw는 헤드+기둥 전체를 돌리고, pitch는 헤드만 끄덕인다.**

서보 버스 케이블은 헤드에서 베이스로 **바깥으로 지나간다**(실물 사진 참고 —
[`assets/robot.jpg`](assets/robot.jpg)). yaw가 돌면 이 케이블이 같이 감기므로,
가동범위를 넓힐 때는 케이블 여유부터 확인할 것.

가동범위가 비대칭인 것(yaw ±90 / pitch ±30)은 **실측으로 정한 값**이고(§0, 2026-07-17),
이 문서는 그 원인을 규명하지 않았다. 기구부를 바꿨으면 원인을 추측하지 말고 §4-5 절차로
다시 재는 것이 맞다.

토크를 내리면(`calibrate_st3215.py stop`) pitch 서보가 헤드 무게를 직접 받는 구조라
**헤드가 처질 수 있다.** 분해·재조립 전에는 헤드를 손으로 받치고 내릴 것.

## 1. 구성 / 배선

```
[셀프파워 USB 허브] ─── [Bus Servo Adapter (CH343)] ─── [yaw ID=1] ─── [pitch ID=2]
                                    │                    (데이지체인)
                          서보 전원은 어댑터 배럴잭 (6~12.6V, USB와 별개)
```

- 어댑터↔MCU 배선은 **3가닥 단선 half-duplex**다(TX/RX 별도 2선이 아님). 다만 **현재
  런타임은 MCU를 경유하지 않는다** — Linux가 pyserial로 직접 구동한다
  ([`00`](00_project_blueprint.md) §2-2).
- **서보 전원(6~12.6V)은 USB와 별개다.** 전원이 없으면 포트는 정상으로 열리는데 ID 1~5가
  전부 무응답이 된다 → COM 포트/ID 문제로 오해하기 쉽다. **어댑터 배럴잭을 먼저 확인.**
- **UNO Q는 USB 호스트 VBUS를 공급하지 않는다** → 셀프파워 허브 필수
  ([`08_troubleshooting.md`](08_troubleshooting.md) §3).

> **서보 CAD(STEP)는 리포에 두지 않는다.** 하우징 설계 때 치수를 맞추려면 ST3215의 3D
> 모델이 필요한데, 이건 서보 제조사가 자사 제품용으로 배포하는 도면이라 우리 리포에
> 재배포할 성질이 아니다. **필요할 때 제조사/판매처 제품 페이지에서 직접 받아 로컬에서만
> 쓴다.** `.gitignore`가 `*.step`을 막고 있으므로 실수로 커밋되지 않는다.
> 참고: `3d_model/`의 STL·3MF·preview는 전부 `3d_model/source/gen_stl_v8_43_complete.py`가 만드는
> 자체 산출물이라 STEP 없이도 빌드된다.

## 2. 왜 EEPROM 중앙 재정의를 쓰는가

raw tick이 물리 중앙에서 벗어나 있으면(캘리브레이션 전 yaw는 3590대였다) 포지션
모드(단일회전 0~4095)에서 한쪽 방향 여유가 부족해진다 — 그때는 +44°밖에 남지 않았다.
EEPROM에서 진짜 중앙(tick 2047)으로 재정의해야 **양쪽 ±90° 여유가 다 확보**되고 멀티턴 모드
없이 필요한 범위가 들어온다.

"raw tick을 코드 상수로만 박아넣기"를 택하지 않은 이유가 이것이다.

## 3. 절대 하지 말 것 — 사고 이력

**torque가 켜진 상태에서 `Homing_Offset`(또는 위치 관련 EEPROM)을 바꾸지 말 것.**

`Present_Position = Actual_Position - Homing_Offset` 관계상 오프셋을 바꾸면
Present_Position이 순간적으로 크게 달라진 것처럼 보인다. 위치 제어 루프가 켜져 있으면
(`Torque_Enable=1`) 서보가 이전 `Goal_Position`과의 오차를 **실제 회전으로 메우려 하면서 큰
폭으로 돌아간다.** 2026-07-17에 이 실수로 **3D 프린트 짐벌 하우징이 파손**됐다.

같은 사고에서 드러난 두 번째 함정:

> **STS3215는 레지스터마다 부호비트 위치가 다르다.**
> `Homing_Offset`(addr 31) = **bit11**, `Present_Position`(addr 56) = **bit15**.
> 양수 값은 두 방식이 우연히 같은 값을 내서 정상처럼 보이지만, **음수 값을 쓰면 완전히 다른
> raw 값**이 저장되어 서보가 엉뚱한 오프셋으로 해석한다.

현재 `scripts/calibrate_st3215.py`의 `calibrate`가 **torque≠0이면 즉시 예외로 중단**하고,
부호비트를 레지스터별로 분리해 인코딩한다. **수동으로 EEPROM을 조작하지 말고 이 명령을 쓸 것.**

상세: [`issues/2026-07-17_01`](issues/2026-07-17_01_homing_offset_wrong_sign_bit_caused_physical_snap.md)

## 4. 재조립 후 확인 절차

짐벌을 분해했다 다시 조립했거나 서보를 교체·재배선했을 때 반드시 거친다.
**§0 표의 값(중앙·방향·ID·가동범위)이 전부 틀어질 수 있다.**

특히 **회전 방향**이 그렇다. "180에서 줄어들면 카메라가 위"는 2026-07-19에 실측한 값이지
코드나 서보의 고유 성질이 아니다. 피치 서보를 반대로 달면 정확히 반대가 된다.

값 자체보다 **확인 절차**를 남겨두는 이유가 이것이다. 검사는 아주 싸다 — 추적을 돌릴
필요도, 사람이 프레임에 있을 필요도 없다.

> **순서가 중요하다: `calibrate` → 방향 확인.**
> `calibrate`는 중앙 기준(EEPROM `Homing_Offset`)을 다시 정의한다. 방향 확인을 먼저 하면
> `150`이 가리키는 물리 각도가 그 뒤에 달라져 버려 검사가 무의미해진다.

### 4-1. 중앙 재정의

짐벌을 **원하는 정면 자세로 손으로 맞춰둔 뒤** 실행한다. 이 명령은 서보를 움직이지 않고
"지금 이 자세"를 중앙(tick 2047 = 180°)으로 재정의한다.

```powershell
# 개발 PC
py -3.14 scripts/calibrate_st3215.py --port COM9 calibrate
```

```bash
# 디바이스에서 직접 (호스트 python3에는 pyserial이 없어 전용 venv를 쓴다)
cd ~/health_care_bot
~/.venvs/hcb/bin/python scripts/calibrate_st3215.py --port /dev/ttyACM0 calibrate
```

`calibrate`가 torque off → 계산 → goal 동기화 → torque on 순서를 자동 처리한다.

**긴급정지**(다른 터미널에서, `move` 도중에도 가능):

```powershell
py -3.14 scripts/calibrate_st3215.py --port COM9 stop     # torque 즉시 OFF
```

### 4-2. pitch 방향 확인

한계각으로 보내고 **눈으로 본다.**

```powershell
py -3.14 scripts/test_st3215_serial.py --port COM9 --id 2 move 150
```

| 카메라가 향하는 곳 | 조치 |
|---|---|
| **위** | `pitch_sign = -1` 유지 (**현재 기본값**) |
| **아래** | `src/ptz_controller.py`의 `pitch_sign` 기본값을 `+1`로 (또는 `--pitch-sign 1`) |

`run.sh`는 `PITCH_SIGN` 환경변수로도 받는다(기본 `-1`): `PITCH_SIGN=1 bash docker/run.sh`.
기동 로그의 `sign : yaw=1 pitch=-1` 줄에서 실제 적용값을 확인할 수 있다.

확인 후 중앙으로 되돌린다: `move 180`

### 4-3. yaw 방향 확인

```powershell
py -3.14 scripts/test_st3215_serial.py --port COM9 --id 1 move 90
```

카메라가 예상과 반대로 돌면 `yaw_sign`을 뒤집는다. 확인 후 `move 180`.

### 4-4. ID 매핑 확인

데이지체인 순서가 바뀌었을 수 있다.

```powershell
py -3.14 scripts/test_st3215_serial.py --port COM9 --id 1 ping
py -3.14 scripts/test_st3215_serial.py --port COM9 --id 2 ping
```

기대값: **ID 1 = yaw(체인 첫 번째), ID 2 = pitch**. 다르면 `ptz_controller.py`의
`yaw_id`/`pitch_id`를 맞추거나 `set-id`로 재지정한다.

> **ST3215는 공장 출하 ID가 모두 1이다.** 체인에 물리기 전에 낱개로 1/2를 나눠 기록해야
> 한다(그대로 체인하면 버스 ID 충돌로 무응답).
> **`set-id`는 즉시 반영된다** — "전원 재투입 필요"라는 일반 SDK 문구와 다르다. 실패 로그가
> 떠도 새 ID로 `ping`해서 실제 상태를 확인할 것
> ([`issues/2026-07-16_01`](issues/2026-07-16_01_servo_id_change_takes_effect_immediately.md)).

### 4-5. 가동범위 재실측

기구부가 바뀌었으면 소프트리밋도 갱신해야 한다. 손으로 천천히 한계까지 돌려보고 각도를 읽는다.

```powershell
py -3.14 scripts/test_st3215_serial.py --port COM9 --id 1 read
```

| 축 | 현재 범위 | 코드 필드 |
|---|---|---|
| yaw | 90 ~ 270° | `yaw_min` / `yaw_max` |
| pitch | 150 ~ 210° | `pitch_min` / `pitch_max` |

**새 범위가 더 좁아졌는데 소프트리밋을 그대로 두면 서보가 기구부에 부딪히며 계속
밀어붙인다.** 반드시 갱신할 것.

## 5. 요약 체크리스트

- [ ] 짐벌을 정면 자세로 맞춘 뒤 `calibrate` 실행 (§4-1)
- [ ] pitch 방향 확인 (`--id 2 move 150` → 위를 보는가) (§4-2)
- [ ] yaw 방향 확인 (`--id 1 move 90`) (§4-3)
- [ ] ID 매핑 확인 (`ping` — yaw=1, pitch=2) (§4-4)
- [ ] 가동범위 재실측 후 소프트리밋 갱신 (§4-5)
- [ ] 확인된 값으로 **본 문서 §0 표를 갱신**

## 6. 벤치 도구 요약

| 스크립트 | 서브커맨드 | 용도 |
|---|---|---|
| `scripts/calibrate_st3215.py` | `calibrate` | ID 1·2 전체 중앙 재정의 (torque off/계산/goal 동기화/on 자동) |
| | `set-center` | 서보 하나만 |
| | `stop` | 긴급정지 (torque 즉시 OFF) |
| `scripts/test_st3215_serial.py` | `ping` / `read` | 응답·위치·전압·온도 확인 |
| | `move` / `sweep` | 단발 이동 / 왕복 |
| | `set-id` | ID 변경 (즉시 반영) |
| | `dual-spin` | 휠 모드 연속 회전 (체인 검증용) |

레지스터 주소·부호비트는 huggingface/lerobot의 feetech 구현으로 검증했다. 새 레지스터를
다룰 때는 **매번 그 테이블과 대조**하고, 이 프로젝트 문서 없이 register map을 추측하지 않는다.

## 7. 관련 문서

- 서보 안전 규칙이 코드에 어떻게 박혀 있는지: [`01_architecture.md`](01_architecture.md) §5-1
- 소프트리밋을 쓰는 추적 로직: [`03_algorithm_ptz_tracking.md`](03_algorithm_ptz_tracking.md) §8
- 사고·함정 원본: [`issues/2026-07-17_01`](issues/2026-07-17_01_homing_offset_wrong_sign_bit_caused_physical_snap.md) ·
  [`issues/2026-07-16_01`](issues/2026-07-16_01_servo_id_change_takes_effect_immediately.md)
- 캘리브레이션·실측 경위: [`history/2026-07-17_01`](history/2026-07-17_01_yaw_pitch_center_calibration_completed.md) ·
  [`history/2026-07-17_02`](history/2026-07-17_02_yaw_pitch_range_of_motion_measured.md) ·
  [`history/2026-07-16_01`](history/2026-07-16_01_st3215_bench_test_tool_and_daisy_chain_verification.md)
