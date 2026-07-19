# 2026-07-17 — yaw/pitch 서보 중앙 캘리브레이션 완료 (실기 사고 극복)

## 시점

2026-07-17

## 사건

ST3215 yaw(ID=1)/pitch(ID=2) 서보를 짐벌에 조립한 뒤, "지금 이 물리
자세를 논리 중앙으로 고정"하는 캘리브레이션을 시도. 중간에 Homing_Offset
레지스터 부호비트를 잘못 가정해 서보가 실제로 크게 회전, 3D 프린트
출력물이 부러지는 사고가 있었다(원인/재발방지는
[`docs/issues/2026-07-17_01_homing_offset_wrong_sign_bit_caused_physical_snap.md`](../issues/2026-07-17_01_homing_offset_wrong_sign_bit_caused_physical_snap.md)).
LeRobot(HuggingFace SO-101, 동일 STS3215 사용) 오픈소스 구현을 참고해
정확한 레지스터 스펙을 확인한 뒤 재시도, 두 서보 모두 물리적 이동 없이
캘리브레이션을 완료했다.

## 배경

기구적으로 확인된 안전 회전 범위: **yaw(1번) ±90°, pitch(2번) ±20°**
(케이블 꼬임 기준). 캘리브레이션 전 raw tick이 물리 중앙(2048)에서 많이
벗어나 있어(yaw 3590대, pitch 3697대 근처), yaw +방향 여유가 +44°밖에
안 남는 문제를 발견 — 서보 자체는 360° 연속회전 가능하지만 포지션 모드
(mode 0)는 tick 0~4095 단일회전 주소만 쓰기 때문에, 멀티턴 모드 없이는
그 이상 못 감. 처음엔 "raw tick을 그대로 코드 상수로 박아넣는" 소프트웨어
전용 방식으로 우회하려 했으나, 사용자가 "그냥 지금을 tick 2048로 만들 수
있냐"고 재질문 — 서보 EEPROM의 Homing_Offset을 실제로 조정하는 쪽이
구조적으로 더 나은 해법(양쪽으로 ±180° 여유 확보, 멀티턴 불필요)이라
다시 시도.

## 결과

- 정확한 레지스터 스펙을 LeRobot 소스로 검증: 주소 31(2바이트),
  `Present_Position = Actual_Position - Homing_Offset`, 부호비트는
  Homing_Offset이 bit11(±2047), Present_Position은 bit15.
- `scripts/test_st3215_serial.py`에 `_encode_sign_magnitude`/`_decode_sign_magnitude`
  (부호비트 파라미터화) + `calibrate_center()`(torque=0 강제 확인 후에만
  동작) 반영, `set-center` 서브커맨드로 노출.
- **torque off 상태에서 재실행 → 두 서보 모두 물리적 이동 없이 정확히
  tick 2047(0~4095 정중앙)로 캘리브레이션 완료** (ID=1 offset=-1117,
  ID=2 offset=-713).
- `ptz/sketch/health_care_ptz.ino`의 `YAW_CENTER_TICK`/`PITCH_CENTER_TICK`을
  원래 기본값 2048로 확정 — 이제 서보 자체 중앙과 소프트웨어 가정이
  실제로 일치하므로 yaw ±90°/pitch ±20° 전부 tick 경계 문제 없이 들어감.

## 다음 단계

- torque를 다시 켜기 전에 Goal_Position을 새 Present_Position(2048)에
  동기화할 것 — 안 그러면 이번과 같은 사고가 재발함(issues 문서 참고).
- 부러진 3D 프린트 출력물 재출력/재조립 필요.
- 재조립 후 `health_care_ptz.ino` 경유 통합 테스트(MCU ↔ 실제 서보)는
  아직 미실시 — 지금까지는 PC 직결 벤치 테스트만 완료.
