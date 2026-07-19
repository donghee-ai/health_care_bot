# 2026-07-16 — ST3215 PC 직결 벤치 테스트 도구 제작 + 데이지체인 반대방향 회전 검증

## 시점

2026-07-16

## 사건

`health_care_ptz.ino`를 거치지 않고 **PC가 USB-TTL 어댑터로 ST3215를
직접 시험**할 수 있는 스크립트(`scripts/test_st3215_serial.py`)를
새로 만들고, 실제 하드웨어 2대(ID=1, ID=2)로 아래를 순서대로 검증했다.

1. USB-TTL 어댑터 인식 확인 — 드라이버 별도 설치 없이 `USB-Enhanced-SERIAL
   CH343`로 COM9에 자동 인식됨.
2. 단품 서보(ID=1) `ping`/`read`(각도·전압·온도)/`move`/`sweep` 정상 동작
   확인. 회전속도 기본값은 `health_care_ptz.ino`의 `BUS_SPEED`(≈569
   tick/s, 20ms/° 환산, 손가락 끼임 방지 기준)와 동일하게 맞춤.
3. 서보 ID를 1→2로 변경(EEPROM `LOCK`/`ID` 레지스터 unlock→write→lock).
   전원 재투입 없이 **즉시 반영**되는 걸 확인 — 상세 원인/재발방지는
   [`docs/issues/2026-07-16_01_servo_id_change_takes_effect_immediately.md`](../issues/2026-07-16_01_servo_id_change_takes_effect_immediately.md).
4. 360° 절대 자기 인코더 특성상 "물리적 중앙"이 원래 없고, 소프트웨어에서
   정의한 각도(90°=tick 2048)가 곧 중앙이라는 점을 확인/공유.
5. 두 서보를 실제 데이지체인으로 연결한 상태에서 휠 모드(연속 회전,
   `MODE=1`)로 전환해 **서로 반대 방향으로 10초간 동시 회전** 시험 →
   종료 후 정지 + 포지션 모드(`MODE=0`) 복귀까지 정상 확인(두 서보 모두
   재확인 `read`에서 정상 응답, 전압 12.2V·온도 32~34°C).

## 배경

지금까지 서보 관련 코드는 전부 Arduino(`health_care_ptz.ino`)를 거쳐
텍스트 프로토콜(`PAN`/`TILT`/`CENTER`)로만 제어했는데, 실기 조립 전
서보 단품 자체의 정상 동작(배선/전원/ID/회전)을 미리 검증할 방법이
없었다. `ptz/sketch/health_care_ptz.ino` 헤더 주석에도 "체인으로 묶기
전에 서보를 하나씩 어댑터에 연결해 ID를 미리 나눠 기록해야 함"이라고
명시돼 있어, 이번에 만든 도구가 그 사전 검증 단계를 그대로 커버한다.

프로토콜은 Feetech SCS/STS 공식 레지스터 맵(체크섬, 명령어, 주소값 —
`ADDR_ACC=41`, `ADDR_GOAL_POSITION_L=42`, `ADDR_MODE=33` 등)을 참고해
pyserial만으로 직접 구현 — Arduino `SMS_STS` 라이브러리와 동일한
레지스터를 건드리므로 PC 시험 결과가 실제 로봇 동작과 그대로 대응된다.

## 결과

- 시험 도구: [`health_care_bot/scripts/test_st3215_serial.py`](../../scripts/test_st3215_serial.py)
  (pyserial 외 의존성 없음, 서브커맨드: `ping`/`read`/`move`/`sweep`/
  `set-id`/`dual-spin`)
- 서보 2대(ID=1, ID=2) 배선·전원·회전 전부 정상, 데이지체인 반대방향
  동시 회전까지 검증 완료 — 짐벌 조립 전 단품/체인 하드웨어 검증 끝.

## 다음 단계

- 실제 짐벌 하우징에 조립 후 물리 중앙과 논리 90°가 어긋나면 OFS
  캘리브레이션(EEPROM offset) 스크립트 추가 필요.
- soak 테스트 및 MCU(`health_care_ptz.ino`) 경유 통합 테스트는 별도
  진행 예정.
