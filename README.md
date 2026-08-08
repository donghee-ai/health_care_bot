# health_care_bot — UNO Q 헬스케어 코치 로봇

Arduino UNO Q (Qualcomm Dragonwing QRB2210, Quad-core Cortex-A53 + STM32U585) 위에서
도는 **단일 도커 컨테이너 / 단일 프로세스** 헬스케어 코치 로봇.

카메라로 자세를 보고 **운동 횟수를 세면서**, **PTZ 짐벌로 사람을 따라가고**,
같은 프로세스가 **모바일 웹앱까지 서빙**한다.

> **문서 지도** — 이 README는 진입점이고, 상세는 `docs/00~09`가 담는다.
> 먼저 [`docs/00_project_blueprint.md`](docs/00_project_blueprint.md)(청사진·현재 상태·문서 지도)를
> 읽고 필요한 파트로 가면 된다. 전체 목록은 §5.

---

## 1. 지금 무엇이 도는가

| # | 기능 | 구현 | 상태 |
|---|---|---|---|
| 1 | **스쿼트** 카운팅 | 무릎 각도 hip-knee-ankle, 히스테리시스 100°↔140° | 동작(임계 실측 튜닝 남음) |
| 2 | **숄더프레스**(팔 위로) 카운팅 | 어깨 올림 각도 elbow-shoulder-hip, 60°↔140° | 동작(임계 실측 튜닝 남음) |
| 3 | **사이드 레터럴 레이즈** 카운팅 | 같은 어깨 올림 각도, 35°↔80° | 동작(임계 실측 튜닝 남음) |
| 4 | **PTZ 자동 추적** | ST3215 버스 서보 2축, 종목별 상체/하체 프레이밍 + 손실 시 관성 복구 | 실기 검증됨 |
| 5 | **웹앱**(`:8080/app`) | 라이브 MJPEG + 카운터 + PTZ 조작 + 텔레메트리 | 실기 동작 |

**종목은 자동 분류하지 않는다.** 세 종목 모두 정면·직립이라 몸 방향으로 구분이 안 되므로
웹 UI에서 명시 선택한다(`POST /api/mode`). 카운터 3개는 항상 동시에 살아 있어 모드를
바꿔도 각자 횟수를 유지한다.

> 푸시업은 2026-07-26에 **제거**했다 — 팔이 카메라 앞뒤(depth)로 굽어 2D 포즈로는
> 팔꿈치 각도가 뭉개진다. 근거: [`docs/04_algorithm_exercise.md`](docs/04_algorithm_exercise.md) §7.

---

## 2. 아키텍처 한눈에

```
[USB 카메라] --(별도 스레드 FrameGrabber: 최신 프레임 1장만 유지)-->
      |
      v
[MoveNet Thunder INT8 / ai-edge-litert, 256x256 letterbox, 4 threads]
      |
      +--> 17 keypoint (y, x, conf)
             |
             +--> angles.py        무릎 / 어깨올림 각도
             |      v
             |    exercise_counter.py   RepCounter (히스테리시스 + dwell) --> rep++
             |
             +--> ptz_controller.py  목표점 산출 -> 섹터/데드존 판정 -> deg/s 제어
             |      v
             |    st3215_bus.py (pyserial, 1 Mbaud, half-duplex)
             |      v
             |    [Bus Servo Adapter] -> [yaw ST3215 ID=1] -> [pitch ID=2]  (데이지체인)
             |
             +--> http_server.py   MJPEG + stats.json + /api/* + /app 정적 서빙
                    v
                  브라우저 http://<UNO_Q_IP>:8080/app
```

**서보는 Linux가 직접 구동한다 — MCU 경유가 아니다.** UNO Q의 STM32U585로 가는 raw
serial 경로가 없어(Router Bridge RPC만 가능) 실기에서 작동 불가였고, 통합 시 걷어냈다.
`ptz/sketch/health_care_ptz.ino`는 그 시절 산물로 **현재 런타임에 쓰이지 않는다.**

상세: [`docs/01_architecture.md`](docs/01_architecture.md)

---

## 3. 빠른 실행

### 3.1 디바이스(UNO Q) — 실제 운용

```bash
ssh arduino@192.168.0.45              # 키 등록됨, 비번 없음
cd ~/health_care_bot
bash docker/run.sh                    # 카메라/서보 노드 자동 탐색 + 기동
```

접속: `http://192.168.0.45:8080/app` (PTZ 조작까지 바로 됨 — 공유 제어권)

중지: `docker stop health-care-bot`

> **실행 전 확인** — `/dev/videoN`·`/dev/ttyACM*` 번호는 **부팅마다 바뀐다.**
> `run.sh`가 이름으로 자동 탐색하지만, 기동 로그의 `camera:` / `serial:` 줄을 꼭 볼 것.
> 수동 지정: `CAMERA_DEV=/dev/video2 bash docker/run.sh`

### 3.2 개발 PC — 서보 직결 테스트

```powershell
cd C:\Project\health_care_bot

# 통합 실행 (웹앱 + 카운팅 + PTZ)
py -3.14 src/main.py models/movenet_thunder_int8.tflite --camera 0 --serial COM9 --serve 8080

# PTZ 추적만 단독 테스트 (OpenCV 창)
py -3.14 scripts/ptz_camera_track.py --port COM9 --camera 0 --drive
```

**반드시 `py -3.14`** — 이 PC의 아나콘다 `base`에는 `cv2`가 없다. 서보 포트는 **COM9**
(CH343, baud 1,000,000)이고, **서보 외부전원(6~12.6V)이 없으면 포트는 열리는데 ID 전부
무응답**이 된다.

### 3.3 모델 준비 (한 번만)

```bash
bash scripts/copy_model.sh    # ../unoq-companion-robot/pose/models/ -> models/
```

---

## 4. 폴더 구조

```
health_care_bot/
├── README.md                   (본 문서 — 진입점)
├── src/                        런타임 (컨테이너가 실행)
│   ├── main.py                 통합 진입점: 루프 + CLI + 텔레메트리
│   ├── pose_utils.py           keypoint 상수 / letterbox / 중심점 헬퍼 / draw
│   ├── angles.py               knee_angle, shoulder_elev_angle, pick_angle
│   ├── exercise_counter.py     RepCounter + Squat/OverheadPress/LateralRaise
│   ├── ptz_controller.py       PTZ 추적 + 손실 복구 + 서보 직결
│   ├── st3215_bus.py           ST3215 프로토콜 저수준 드라이버
│   ├── http_server.py          MJPEG + stats.json + /api/* + /app 서빙
│   └── app_state.py            세션 상태 + 운영자 PIN 제어권 lock
├── web/                        Vite + React PWA (시안 6종) — 빌드 산출물 web/dist
│   ├── dist/index.html         ★ 현재 /app으로 서빙되는 애플 "Fluid" 정적 페이지
│   ├── dist/index.html.stock.bak   stock React 빌드 백업
│   ├── ARCHITECTURE.md         웹 설계 근거 ("왜 이렇게")
│   └── DESIGN.md               시안·서체·색 결정 근거 (07-21 기준, 일부 오래됨)
├── design_demos/               독립 HTML 시안 2종 (Fluid 원본 / Field Optics)
├── docker/
│   ├── Dockerfile              Ubuntu 22.04 + python3.10 + ai-edge-litert + pyserial
│   ├── requirements.txt
│   └── run.sh                  빌드 + 실행 (카메라/시리얼 노드 자동 탐색)
├── models/movenet_thunder_int8.tflite
├── scripts/                    벤치·도구 (런타임 아님)
│   ├── calibrate_st3215.py     중앙 재캘리브레이션 / 긴급정지
│   ├── test_st3215_serial.py   ping/read/move/sweep/set-id/dual-spin
│   ├── ptz_camera_track.py     PTZ 단독 테스트 (작업본, v1/v2 백업 동봉)
│   ├── mock_serve.py           카메라·모델 없이 프론트만 검증
│   └── copy_model.sh
├── ptz/sketch/                 MCU 스케치 — 현재 미사용 (MCU 트랙 보류)
├── stl/                        짐벌 하우징 3D 모델
├── docs/                       ← 아래 §5
└── backup/                     복원점 3개 (pre_web_integration 등)
```

---

## 5. 문서 지도

| # | 문서 | 무엇을 담는가 |
|---|---|---|
| 00 | [`00_project_blueprint.md`](docs/00_project_blueprint.md) | **청사진** — 목적·실측 현황·검증 상태·문서 지도 |
| 01 | [`01_architecture.md`](docs/01_architecture.md) | 프로세스/스레드, 모듈 경계, 상태 소유권, degrade 경로 |
| 02 | [`02_http_api_and_stats.md`](docs/02_http_api_and_stats.md) | HTTP API 계약 + `stats.json` 전체 스키마 |
| 03 | [`03_algorithm_ptz_tracking.md`](docs/03_algorithm_ptz_tracking.md) | PTZ 제어 법칙 + 관성 손실 복구 + 튜닝 |
| 04 | [`04_algorithm_exercise.md`](docs/04_algorithm_exercise.md) | 종목별 각도·카운팅 상태기계 + 실패 모드 |
| 05 | [`05_web_ui_fluid.md`](docs/05_web_ui_fluid.md) | 웹 UI (Fluid) — 화면·조작·배포 |
| 06 | [`06_hardware_calibration.md`](docs/06_hardware_calibration.md) | 하드웨어 현재값 + 캘리브레이션/재조립 절차 |
| 07 | [`07_runbook.md`](docs/07_runbook.md) | 실행·배포 런북 (디바이스/PC, 환경 확인) |
| 08 | [`08_troubleshooting.md`](docs/08_troubleshooting.md) | 증상 → 원인 함정 색인 |
| 09 | [`09_performance_roadmap.md`](docs/09_performance_roadmap.md) | 성능 실측 + 다음 할 일 우선순위 |
| — | [`docs/history/`](docs/history/) · [`docs/issues/`](docs/issues/) | 기록(append-only) — 한 사건 한 파일 |
| — | [`docs/history/2026-07-26_05_session_handoff.md`](docs/history/2026-07-26_05_session_handoff.md) | **가장 최신 세션 맥락** |
| — | [`web/ARCHITECTURE.md`](web/ARCHITECTURE.md) · [`APP_GUIDE.md`](APP_GUIDE.md) | 웹앱 설계 근거 / React 시절 실행 가이드(일부 낡음) |

---

## 6. CLI 옵션 (자주 쓰는 것)

전체는 `python3 src/main.py --help`.

| 플래그 | 기본 | 의미 |
|---|---|---|
| `--mode` | `squat` | `squat` / `overhead` / `lateral`. 웹 `/api/mode`로 실시간 변경됨 |
| `--camera` | `0` | `/dev/videoN` 인덱스 |
| `--serial` | (없음) | 서보 버스 포트. **미지정 시 PTZ disabled**로 degrade |
| `--serve` | `0` | HTTP 포트 (0 = 비활성) |
| `--conf` | `0.3` | keypoint confidence 임계 |
| `--side` | `better` | 좌/우 각도 선택: 둘 다 보이면 평균, 한쪽만 보이면 그쪽 |
| `--squat-down-th` / `--squat-up-th` | 100 / 140 | 스쿼트 임계 |
| `--overhead-down-th` / `--overhead-up-th` | 60 / 140 | 숄더프레스 임계 |
| `--lateral-down-th` / `--lateral-up-th` | 35 / 80 | 레터럴 임계 |
| `--min-dwell-ms` | `200` | 상태 전환 후 최소 유지 시간 |
| `--idle-skip-draw` | off | 스트림 뷰어 0명이면 그리기+인코딩 skip (연산 집중 모드) |
| `--sector-side` | `1/6` | 좌우 섹터 폭 → 중앙 4/6 밴드 유지 |
| `--pitch-target-y` / `--pitch-deadzone` | 0.62 / 0.20 | 하체(스쿼트) 프레이밍 |
| `--track-scale` / `--both-knee-scale` | 0.5 / 0.5 | 추적 속도 배율 (양 무릎 보이면 총 1/4) |
| `--frame-out-grace` | `15` | 미검출 N프레임 후 LOST 표시 |

PTZ 파라미터의 의미와 튜닝 지침: [`docs/03_algorithm_ptz_tracking.md`](docs/03_algorithm_ptz_tracking.md) §11.

---

## 7. 안전 / 운영 규칙

- **서보 EEPROM은 torque가 켜진 상태에서 절대 건드리지 말 것.** torque on 상태로
  `Homing_Offset`을 바꾸면 서보가 옛 `Goal_Position`으로 실제 회전한다 —
  이 실수로 **3D 출력물이 파손된 이력**이 있다. 캘리브레이션은 반드시
  `scripts/calibrate_st3215.py calibrate`로 (torque off → 계산 → goal 동기화 → on을
  자동 처리). 상세: [`docs/issues/2026-07-17_01`](docs/issues/2026-07-17_01_homing_offset_wrong_sign_bit_caused_physical_snap.md)
- **긴급정지**: 다른 터미널에서 `py -3.14 scripts/calibrate_st3215.py --port COM9 stop`
- **실측 가동범위** (2026-07-17): yaw(ID=1) 중앙 180° ±90°, pitch(ID=2) 중앙 180° ±30°.
  코드 소프트리밋(`yaw_min/max`, `pitch_min/max`)이 이 값이다. 기구부를 바꿨으면
  [`docs/06_hardware_calibration.md`](docs/06_hardware_calibration.md) §4로 재확인 후 갱신.
- **회전 속도는 569 tick/s(≈50 deg/s, 옛 PWM 20ms/° 등가) 고정** — 추적 중에도 동일.
  손가락 끼임 방지 목적이므로 올리지 말 것.
- **ST3215는 공장 출하 ID가 모두 1** — 체인에 물리기 전에 낱개로 yaw=1/pitch=2를
  나눠 기록해야 한다. ID 변경은 **즉시 반영**된다("전원 재투입 필요"라는 일반 SDK
  문구와 다름): [`docs/issues/2026-07-16_01`](docs/issues/2026-07-16_01_servo_id_change_takes_effect_immediately.md)
- **HTTP는 인증이 없다.** 운영자 mutation만 PIN(`1234`, `src/app_state.py`) 기반
  제어권 lock으로 막혀 있고 조회·스트림은 무인증이다. **로컬 LAN 외부 노출 금지**,
  시연 전 PIN 교체 권장.
- **UNO Q는 USB 호스트 VBUS가 꺼져 있다** — 버스파워 허브/장치는 인식되지 않는다.
  **셀프파워(외부전원) USB 허브 필수.** 카메라·서보가 *둘 다* 안 잡히면 개별 장치가
  아니라 허브 전원부터 의심할 것.

---

## 8. 자주 밟는 함정

| 함정 | 요약 | 상세 |
|---|---|---|
| 디바이스 노드 번호 | `/dev/videoN`·`ttyACM/ttyUSB`가 부팅마다 바뀐다. 번호를 규칙으로 적지 말고 **이름으로 식별** | [issues/2026-07-19_01](docs/issues/2026-07-19_01_device_node_names_are_not_stable.md) |
| argparse ↔ run.sh 동기화 | `--mode` choices를 바꾸면 `run.sh`(및 Dockerfile CMD)의 하드코딩 인자도 같이 고쳐야 한다. `--rm`이라 `docker logs`에 안 남음 | [history/2026-07-26_02](docs/history/2026-07-26_02_pushup_removed_overhead_lateral_added.md) |
| `npm run build`가 Fluid를 덮음 | `/app`은 자체포함 정적 HTML이라 React 빌드 대상이 아니다. 빌드하면 stock으로 덮인다 | [docs/05](docs/05_web_ui_fluid.md) §9-1 |
| 폰 접속 실패 | `ERR_ADDRESS_UNREACHABLE` = 폰 **랜덤 MAC**(서버 문제 아님) | [issues/2026-07-26_01](docs/issues/2026-07-26_01_mobile_web_access_fails_random_mac.md) |
| `cv2.CAP_PROP_BUFFERSIZE` | 드라이버가 무시한다. `FrameGrabber`(최신 프레임만 유지)로 해결됨 | [issues/2026-07-11_04](docs/issues/2026-07-11_04_camera_buffer_accumulation_causes_growing_latency.md) |
| `adb push` | Git Bash는 경로를 변환해 조용히 실패 → **PowerShell로**. 디렉토리는 remote `rm -rf` 먼저(안 하면 `src/src/` 중첩) | [issues/2026-07-11_01](docs/issues/2026-07-11_01_adb_push_msys_path_mangling.md), [_02](docs/issues/2026-07-11_02_adb_push_directory_nests_when_remote_exists.md) |
| cp949 콘솔 크래시 | em-dash·⚠ 같은 문자를 **코드/주석**에 쓰면 Windows 콘솔에서 `UnicodeEncodeError` | [docs/08](docs/08_troubleshooting.md) §7 |

전체 목록은 [`docs/08_troubleshooting.md`](docs/08_troubleshooting.md) — 증상에서 원인으로
가는 색인 + `issues/` 전체 목록이 있다.

---

## 9. 성능 (실측)

| 항목 | 값 | 비고 |
|---|---|---|
| 추론 FPS | ~11.4 | **invoke(추론) 바운드**. 인코딩 on/off 차이 ~0 |
| 루프 지연 | ~90 ms | grab → invoke → draw → encode 직렬 |
| CPU | ~83% (4코어 합산 100% 기준) | 이미 warning 구간, 여유 17% |
| CPU 클럭 | 2016 MHz 전 코어 = 최대 | 거버너로 더 올릴 여지 없음 |
| 온도 | 51~73°C | throttle 전 |

FPS를 올리는 유일한 큰 레버는 **NPU/DSP 델리게이트**(Hexagon HTP · QNN/LiteRT)다 —
이 CPU에는 `asimddp`(INT8 dotprod)가 없어 INT8 고속 커널을 못 쓴다. 근거와 착수 지점:
[`docs/history/2026-07-21_02`](docs/history/2026-07-21_02_session_handoff.md) §4.

---

## 10. 모델 / 라이센스

- 추론 모델: **MoveNet Thunder INT8** (`movenet_thunder_int8.tflite`, ~6.8 MB) —
  기존 pose 라인 자산 재사용. git에 미포함 (`scripts/copy_model.sh`로 복사).
- 본 라인 코드: MIT.
