# health_care_bot — UNO Q 헬스케어 로봇

Arduino UNO Q (Qualcomm Dragonwing QRB2210, Quad-core Cortex-A53 + STM32U585) 위에서 도는 **단일 도커 컨테이너** 헬스케어 코치 로봇.

## 기능

| # | 기능 | 모듈 | 상태 |
|---|---|---|---|
| 1 | 스쿼트 카운팅 | `src/exercise_counter.py::SquatCounter` | 무릎 각도 hip-knee-ankle, hysteresis 100°↔140° |
| 2 | 팔굽혀 펴기 카운팅 | `src/exercise_counter.py::PushupCounter` | 팔꿈치 각도 shoulder-elbow-wrist, hysteresis 90°↔160° |
| 3 | PTZ 자동 추적 | `src/ptz_controller.py` + `ptz/sketch/health_care_ptz.ino` | 사람 프레임-아웃 검출 시 pan/tilt 보정 |

운동 종목은 `--mode {squat,pushup,auto}`로 선택. `auto`는 어깨-엉덩이 라인 각도로 자세를 분류 (수직 → squat, 수평 → pushup).

## 아키텍처 (단일 컨테이너 1-process)

```
[USB 카메라 /dev/video0]
        │  cv2.VideoCapture
        ↓
[MoveNet Thunder INT8] ← src/pose_utils.py (letterbox 256×256)
        │  ai-edge-litert (XNNPACK, 4 threads)
        ↓
[17 keypoint (y,x,conf)]
        │
        ├─→ src/angles.py  → knee_angle / elbow_angle
        │        ↓
        │   src/exercise_counter.py
        │        ↓  rep++ 이벤트
        │
        ├─→ src/ptz_controller.py  → frame-out 판정
        │        ↓  serial write "PAN <delta>\n" / "TILT <delta>\n"
        │   [USB-Serial /dev/ttyACM0]
        │        ↓
        │   ptz/sketch/health_care_ptz.ino (STM32U585)
        │        ↓  UART(Serial1) → SCServo WritePosEx (~20ms/° 환산 speed)
        │   [Bus Servo Adapter] → [Yaw 서보 ST3215 ID=1] → [Pitch 서보 ID=2]
        │        (데이지체인, 어댑터가 전원+제어회로 통합)
        │
        └─→ src/http_server.py  → MJPEG + stats.json
                 ↓
            브라우저 http://<UNO_Q_IP>:8080/
```

## 폴더 구조

```
health_care_bot/
├── README.md                       (본 문서)
├── docker/
│   ├── Dockerfile                  Ubuntu 22.04 + python3.10 + ai-edge-litert + pyserial
│   ├── requirements.txt
│   └── run.sh                      build + run (--device camera + tty 마운트)
├── models/
│   └── README.md                   movenet_thunder_int8.tflite 복사 안내
├── src/
│   ├── main.py                     통합 진입점 — argparse + 루프
│   ├── pose_utils.py               KP / SKELETON / letterbox / unletterbox / draw
│   ├── angles.py                   angle_3pt, knee_angle, elbow_angle, body_orientation
│   ├── exercise_counter.py         RepCounter base + SquatCounter + PushupCounter
│   ├── ptz_controller.py           frame-out 판정 + 시리얼 송신
│   └── http_server.py              MJPEG + stats.json
├── ptz/
│   └── sketch/
│       └── health_care_ptz.ino     yaw/pitch ST3215 버스 서보 제어 (~20ms/° 환산 speed)
└── scripts/
    ├── copy_model.sh               unoq-companion-robot/pose/models/ → 본 라인 복사
    ├── st3215_bus.py               ST3215 프로토콜 공용 저수준 모듈 (아래 두 스크립트가 공유)
    ├── test_st3215_serial.py       PC 직결 벤치 테스트 (ping/read/move/sweep/set-id/dual-spin)
    └── calibrate_st3215.py         재조립 후 중앙 재캘리브레이션 (calibrate/set-center/stop)
```

## 빠른 실행

### 1. 모델 복사 (한 번만)

```bash
bash scripts/copy_model.sh
# → models/movenet_thunder_int8.tflite 가 생성됨
```

### 2. Arduino 측 sketch 플래시 (한 번만)

하드웨어: ST3215 시리얼 버스 서보 2개를 Bus Servo Adapter로 데이지체인 —
`어댑터 → yaw(첫 번째) → pitch(yaw에서 체인)`. 어댑터는 UNO Q MCU와 TTL UART
(Serial1, USB 브릿지용 Serial과는 별도 채널)로 연결하고, 서보 전원은 어댑터
쪽 전용 커넥터로 공급 (GND 공통 필수).

⚠ 체인으로 묶기 **전에** 서보를 하나씩 연결해 ID를 yaw=1 / pitch=2 로 미리
나눠 기록할 것 — 두 서보 모두 공장 출하 ID가 1이라 그대로 체인에 물리면
버스 ID가 충돌해 응답하지 않음.

Feetech `SCServo` 라이브러리(SMS_STS 클래스) 설치 후 `ptz/sketch/health_care_ptz.ino`를
Arduino IDE 또는 `arduino-cli`로 STM32U585에 업로드. USB(Python 브릿지) 시리얼은
기존과 동일하게 115200 baud, 버스 서보 쪽은 ST3215 공장 기본값인 1,000,000 baud.

### 2.5 짐벌 재조립 후 중앙 재캘리브레이션

짐벌을 분해/재조립했다면, 원하는 정면(중앙) 자세로 손으로 맞춰둔 상태에서:

```powershell
python scripts/calibrate_st3215.py --port COM9 calibrate
```

torque off → 현재 물리 위치를 tick 2047(정중앙)로 EEPROM 재정의(서보는 안 움직임)
→ Goal_Position 동기화 → torque 재활성화까지 자동으로 안전하게 처리한다
(원리/사고 이력은 `docs/issues/2026-07-17_01_homing_offset_wrong_sign_bit_caused_physical_snap.md`).

긴급 정지가 필요하면 다른 터미널에서:

```powershell
python scripts/calibrate_st3215.py --port COM9 stop
```

### 3. 컨테이너 빌드 + 실행

```bash
bash docker/run.sh                   # 빌드 (최초만) + 인터랙티브 진입
# 컨테이너 안에서:
python3 /work/src/main.py \
    /work/models/movenet_thunder_int8.tflite \
    --mode auto --camera 0 --serial /dev/ttyACM0 --serve 8080
```

브라우저 http://<UNO_Q_IP>:8080/ → 라이브 카메라 + REPS 카운터 + PTZ 상태.

## 옵션 요약

| 플래그 | 기본 | 의미 |
|---|---|---|
| `--mode` | `auto` | `squat` / `pushup` / `auto` (자세로 자동) |
| `--camera` | `0` | `/dev/videoN` 인덱스 |
| `--serial` | `(none)` | Arduino 시리얼 포트. 미지정 시 PTZ 비활성 |
| `--serve` | `0` | HTTP 포트 (0 = 비활성) |
| `--frame-out-margin` | `0.15` | 화면 가장자리 N% 안쪽이면 frame-out 판정 |
| `--frame-out-grace` | `15` | 미검출 N프레임 후 PTZ 트리거 |
| `--conf` | `0.3` | keypoint confidence 임계 |

전체 옵션: `python3 src/main.py --help`.

## 안전 / 운영

- HTTP 서버는 **인증 없음** — 디버그용. 로컬 LAN 외부 노출 금지.
- 서보 회전 속도는 기존 PWM 기준 `20ms/°` (180° = 3.6초)를 ST3215 native speed로 환산해 유지 — 추적 시에도 동일. 손가락 끼임 방지. 실기 가감속(ACC) 튜닝 후 재검증 필요.
- 미검출 grace period (`--frame-out-grace`) 이내에는 PTZ 정지 — 일시 가림 (드롭) 시 흔들림 방지.
- ST3215는 공장 출하 ID가 모두 1 — 체인 연결 전 낱개로 yaw=1/pitch=2 ID를 나눠 기록해야 함 (그대로 체인하면 버스 충돌).
- 실기 가동범위 실측 완료(2026-07-17): **yaw(ID=1) 중앙 ±90°, pitch(ID=2) 중앙 ±30°** — 전 구간 전압/온도 이상 없이 확인됨. `health_care_ptz.ino`의 `YAW_MIN/MAX`, `PITCH_MIN/MAX`에 반영됨.
- 서보 EEPROM(Homing_Offset 등)은 **torque가 켜진 상태에서 절대 건드리지 말 것** — torque on 상태로 offset을 바꾸면 서보가 옛 Goal_Position으로 실제 회전해 부품이 파손될 수 있음(실기 사고 이력 있음). `scripts/calibrate_st3215.py`의 `calibrate`가 이 순서를 안전하게 자동 처리하니 수동으로 EEPROM을 조작하지 말 것.

## 모델 / 라이센스

- 추론 모델: MoveNet Thunder INT8 (`movenet_thunder_int8.tflite`, ~6.8 MB) — 기존 pose 라인 자산 재사용.
- 본 라인 코드: MIT.
