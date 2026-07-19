# ST3215 Homing_Offset 잘못된 부호비트로 실제 회전 → 출력물 파손

## 증상

짐벌 조립 상태에서 "지금 물리 위치를 논리 중앙으로 캘리브레이션"하려고
서보 EEPROM의 Position Correction(Homing_Offset, addr 31~32) 레지스터에
음수 오프셋을 썼는데, 서보가 갑자기 실제로 크게 회전해버렸고 그 과정에서
3D 프린트 출력물(짐벌 하우징)이 부러졌다. Present_Position 계산도
매번 다른 이상한 값이 나와 예측이 전혀 안 됐다.

## 원인

두 가지가 겹쳤다.

1. **부호비트 위치를 잘못 가정함.** Present_Position 레지스터는
   bit15가 부호비트(매그니튜드 15bit)인데, **Homing_Offset 레지스터는
   STS3215에서 bit11이 부호비트**(매그니튜드 최대 ±2047)다. 이 스크립트는
   처음에 두 레지스터 모두 bit15로 인코딩했다 — 양수 값(예: +100)은
   부호비트가 애초에 0이라 우연히 두 방식이 같은 값을 내서 정상 동작하는
   것처럼 보였지만, **음수 값을 쓰면 완전히 다른(부호비트 위치가 어긋난)
   raw 값**이 저장되어 서보가 엉뚱한 오프셋으로 해석했다.
2. **torque가 켜진 상태에서 오프셋을 바꿈.** Present_Position =
   Actual_Position - Homing_Offset 관계상, 오프셋을 바꾸면 Present_Position이
   순간적으로 크게 달라진 것처럼 보인다. 서보 내부 위치 제어 루프가 켜져
   있으면(Torque_Enable=1), 이 "달라진" Present_Position과 이전에 남아있던
   Goal_Position(직전 수동 `move` 테스트에서 보낸 값) 사이의 오차를 실제
   회전으로 메우려고 하면서 큰 폭의 예상치 못한 회전이 발생했다. 이게
   출력물 파손의 직접 원인.

정확한 레지스터 주소/공식/부호비트는 STS3215와 동일 모터를 쓰는
LeRobot(HuggingFace SO-101/SO-100 로봇팔)의 공식 오픈소스 구현으로 확인:
- 주소: [`feetech/tables.py`](https://github.com/huggingface/lerobot/blob/main/src/lerobot/motors/feetech/tables.py) — `Homing_Offset: (31, 2)`
- 공식: [`feetech.py`](https://github.com/huggingface/lerobot/blob/main/src/lerobot/motors/feetech/feetech.py) `_get_half_turn_homings` 주석 — `Present_Position = Actual_Position - Homing_Offset`
- 부호비트: [`feetech/tables.py`](https://github.com/huggingface/lerobot/blob/main/src/lerobot/motors/feetech/tables.py) `MODEL_ENCODING_TABLE` — `Homing_Offset: 11`, `Present_Position: 15`
- 인코딩 방식: [`encoding_utils.py`](https://github.com/huggingface/lerobot/blob/main/src/lerobot/motors/encoding_utils.py) `encode_sign_magnitude`/`decode_sign_magnitude`

## 해결

`scripts/test_st3215_serial.py` 수정:
- `_encode_sign_magnitude(value, sign_bit_index)` / `_decode_sign_magnitude(raw, sign_bit_index)`로
  부호비트 위치를 파라미터화. `Present_Position`은 15, `Homing_Offset`은 11로 분리.
- `calibrate_center()`가 실행 전 **Torque_Enable을 직접 읽어서 0이 아니면
  즉시 예외를 던지고 중단**하도록 안전장치 추가 — 앞으로 이 사고가 재발할
  방법 자체를 차단.
- 캘리브레이션 목표를 LeRobot과 동일한 컨벤션(`Homing_Offset = Actual_Position - 2047`,
  즉 tick 0~4095의 정중앙)으로 통일.

수정 후 torque off 상태에서 재실행해 두 서보 모두 물리적 이동 없이
정확히 tick 2047로 캘리브레이션 완료 확인(상세는
[`docs/history/2026-07-17_01_yaw_pitch_center_calibration_completed.md`](../history/2026-07-17_01_yaw_pitch_center_calibration_completed.md)).

## 재발 방지

- **STS3215 계열 레지스터는 신호(sign) 비트 위치가 레지스터마다 다르다** —
  Present_Position(15)과 Homing_Offset(11)을 혼동하지 말 것. 새 레지스터를
  다룰 땐 매번 LeRobot의 `feetech/tables.py`(`MODEL_ENCODING_TABLE`)로
  대조 확인한다. 이 프로젝트 자체 문서 없이 register map을 추측하지 않는다.
- **Torque_Enable=1인 상태에서 Homing_Offset(또는 다른 위치 관련 EEPROM
  레지스터)을 바꾸지 않는다** — 반드시 먼저 torque off, 캘리브레이션 완료
  후 torque를 다시 켜기 전에 Goal_Position을 새 Present_Position에 맞춰
  동기화한다.
- 작은 테스트 값(예: +100)으로 먼저 검증하고 확대 적용하는 습관이 이번에
  진짜 원인(부호비트 위치)을 찾는 데 결정적이었다 — 앞으로도 레지스터
  실험은 작은 값 → 검증 → 확대 순서로.
