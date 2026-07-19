# 짐벌 재조립 후 확인 체크리스트

짐벌을 분해했다 다시 조립했거나, 서보를 교체·재배선했을 때 반드시 거칠 것.

## 왜 필요한가

HANDOFF §3에 적힌 값들 — **중앙 기준, 회전 방향, ID 매핑, 가동범위** — 은
전부 **지금의 물리적 장착 상태에 의존하는 값**이다. 서보를 뒤집어 달거나
데이지체인 순서가 바뀌면 그대로 틀린 값이 된다.

특히 **회전 방향**이 그렇다. "180에서 줄어들면 카메라가 위"는 2026-07-19에
실측한 값이지, 코드나 서보의 고유 성질이 아니다. 피치 서보를 반대로 달면
정확히 반대가 된다.

값 자체보다 **확인 절차**를 남겨두는 이유가 이것이다. 검사는 아주 싸다 —
추적을 돌릴 필요도, 사람이 프레임에 있을 필요도 없다.

## 순서가 중요하다

**반드시 `calibrate` -> 방향 확인 순서로 한다.**

`calibrate`는 중앙 기준(EEPROM `Homing_Offset`)을 다시 정의한다. 방향 확인을
먼저 하면 `150`이 가리키는 물리 각도가 그 뒤에 달라져 버려 검사가 무의미해진다.

---

## 1. 중앙 재정의

짐벌을 **원하는 정면 자세로 손으로 맞춰둔 뒤** 실행한다. 이 명령은 서보를
움직이지 않고 "지금 이 자세"를 중앙(tick 2047 = 180도)으로 재정의한다.

```powershell
py -3.14 scripts/calibrate_st3215.py --port COM9 calibrate
```

> **직접 EEPROM을 건드리지 말 것.** torque가 켜진 상태로 `Homing_Offset`을
> 바꾸면 서보가 옛 `Goal_Position`으로 실제 회전한다. 과거 이 실수로 3D
> 출력물이 파손된 이력이 있다 (`issues/2026-07-17_01_...`).
> `calibrate` 명령이 torque off -> 계산 -> goal 동기화 -> on 순서를 자동
> 처리하므로 반드시 이걸 쓴다.

긴급 정지가 필요하면 다른 터미널에서:

```powershell
py -3.14 scripts/calibrate_st3215.py --port COM9 stop
```

## 2. 회전 방향 확인 (pitch)

한계각으로 보내고 **눈으로 본다.**

```powershell
py -3.14 scripts/test_st3215_serial.py --port COM9 --id 2 move 150
```

| 카메라가 향하는 곳 | 조치 |
|---|---|
| **위** | `pitch_sign = +1` 유지 (현재 기본값) |
| **아래** | `src/ptz_controller.py`의 `pitch_sign` 기본값을 `-1`로 |

확인 후 중앙으로 되돌린다: `move 180`

## 3. 회전 방향 확인 (yaw)

```powershell
py -3.14 scripts/test_st3215_serial.py --port COM9 --id 1 move 90
```

카메라가 예상과 반대로 돌면 `yaw_sign`을 뒤집는다. 확인 후 `move 180`.

## 4. ID 매핑 확인

데이지체인 순서가 바뀌었을 수 있다.

```powershell
py -3.14 scripts/test_st3215_serial.py --port COM9 --id 1 ping
py -3.14 scripts/test_st3215_serial.py --port COM9 --id 2 ping
```

기대값: **ID 1 = yaw(체인 첫 번째), ID 2 = pitch**. 다르면 `ptz_controller.py`의
`yaw_id` / `pitch_id`를 맞추거나, `set-id`로 서보 ID를 재지정한다.

> `set-id`는 **즉시 반영**된다. "전원 재투입 필요"라는 일반 SDK 문구와 다르니,
> 실패 로그가 떠도 새 ID로 `ping`해서 확인할 것 (`issues/2026-07-16_01_...`).

## 5. 가동범위 재실측

기구부가 바뀌었으면 소프트리밋도 갱신해야 한다. 손으로 천천히 한계까지
돌려보고 각도를 읽는다.

```powershell
py -3.14 scripts/test_st3215_serial.py --port COM9 --id 1 read
```

현재 값 (2026-07-17 실측):

| 축 | 범위 | 코드 필드 |
|---|---|---|
| yaw | 90~270도 (중앙 ±90) | `yaw_min` / `yaw_max` |
| pitch | 150~210도 (중앙 ±30) | `pitch_min` / `pitch_max` |

새 범위가 더 좁아졌는데 소프트리밋을 그대로 두면 **서보가 기구부에 부딪히며
계속 밀어붙인다.** 반드시 갱신할 것.

---

## 요약 체크리스트

- [ ] 짐벌을 정면 자세로 맞춘 뒤 `calibrate` 실행
- [ ] pitch 방향 확인 (`--id 2 move 150` -> 위를 보는가)
- [ ] yaw 방향 확인 (`--id 1 move 90`)
- [ ] ID 매핑 확인 (`ping` — yaw=1, pitch=2)
- [ ] 가동범위 재실측 후 소프트리밋 갱신
- [ ] 확인된 값으로 HANDOFF §3 표 갱신
