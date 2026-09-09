# health_care_bot — UNO Q 헬스케어 코치 로봇

Arduino UNO Q (Qualcomm Dragonwing QRB2210, Quad-core Cortex-A53 + STM32U585) 위에서
도는 **단일 도커 컨테이너 / 단일 프로세스** 헬스케어 코치 로봇.

카메라로 자세를 보고 **운동 횟수를 세면서**, **PTZ 짐벌로 사람을 따라가고**,
같은 프로세스가 **모바일 웹앱까지 서빙**한다.

> **문서 지도** — 이 README는 진입점이고, 상세는 `docs/00~09`가 담는다.
> 먼저 [`docs/00_project_blueprint.md`](docs/00_project_blueprint.md)(청사진·현재 상태·문서 지도)를
> 읽고 필요한 파트로 가면 된다. 전체 목록은 §5.

> **자매 리포** — 이 로봇이 쓰는 MoveNet Thunder INT8은
> [`donghee-ai/unoq-edge-ai-lines`](https://github.com/donghee-ai/unoq-edge-ai-lines)에서 왔다.
> 그쪽은 같은 UNO Q(QRB2210, NPU 없음)에서 **Vision · ASR · Pose · KWS 네 라인을 CPU만으로**
> 돌린 PoC와 실측 기록이고, 이 리포는 그중 Pose 자산으로 만든 **제품 라인**이다.
> (현재 private — 접근 권한이 없으면 404가 뜬다)

---

## 1. 지금 무엇이 도는가

| # | 기능 | 구현 | 상태 |
|---|---|---|---|
| 1 | **스쿼트** 카운팅 | 무릎 각도 hip-knee-ankle, 히스테리시스 100°↔140° | 동작(임계 실측 튜닝 남음) |
| 2 | **숄더프레스**(팔 위로) 카운팅 | 어깨 올림 각도 elbow-shoulder-hip, 60°↔140° | 동작(임계 실측 튜닝 남음) |
| 3 | **사이드 레터럴 레이즈** 카운팅 | 같은 어깨 올림 각도, 35°↔80° | 동작(임계 실측 튜닝 남음) |
| 4 | **PTZ 자동 추적** | ST3215 버스 서보 2축, 종목별 상체/하체 프레이밍 + 손실 시 관성 복구 | 실기 검증됨 |
| 5 | **웹앱**(`:8080/app`) | 라이브 MJPEG + 카운터 + PTZ 조작 + 텔레메트리 | 실기 동작 |
| 6 | **경비 모드** | 운동과 분리된 4번째 모드. 전환 즉시 홈 정렬 → 5초 무장 → 사람 감지 시 추적+자동촬영(`captures/`) → 10초 미검출 시 홈 복귀. 웹에서 수동 촬영/사진 갤러리도 가능 | 실기 검증됨 |
| 7 | **원격 접속**(Tailscale Funnel) | 같은 Wi-Fi가 아니어도 외부에서 `/app` 접속 가능 | 실기 검증됨(§3.2) |

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

**서보는 Linux가 직접 구동한다 — MCU 경유가 아니다.** ST3215 버스 서보 어댑터를 USB
허브로 UNO Q에 물려, Linux(pyserial)가 바로 제어한다. `ptz/sketch/health_care_ptz.ino`는
그 이전 MCU 경유 설계의 산물로 **현재 런타임에 쓰이지 않는다.**

상세: [`docs/01_architecture.md`](docs/01_architecture.md)

---

## 3. 빠른 실행

### 3.1 디바이스(UNO Q) — 실제 운용

```bash
ssh arduino@192.168.0.50              # 사설 LAN. 접속 정보는 기기에서 확인
cd ~/health_care_bot
bash docker/run.sh                    # 카메라/서보 노드 자동 탐색 + 기동
```

접속: `http://192.168.0.50:8080/app` (PTZ 조작까지 바로 됨 — 공유 제어권)

중지: `docker stop health-care-bot`

> **실행 전 확인** — `/dev/videoN`·`/dev/ttyACM*` 번호는 **부팅마다 바뀐다.**
> `run.sh`가 이름으로 자동 탐색하지만, 기동 로그의 `camera:` / `serial:` 줄을 꼭 볼 것.
> 수동 지정: `CAMERA_DEV=/dev/video2 bash docker/run.sh`
>
> **IP도 DHCP라 공유기 재부팅 시 바뀔 수 있다** (2026-08-08에 `.45`→`.50`로 실제로
> 바뀜). 안 붙으면 `arp -a` / ping 스캔으로 재탐색. 상세: [`08_troubleshooting.md`](docs/08_troubleshooting.md).

### 3.2 원격 접속 — 같은 Wi-Fi가 아니어도 (Tailscale Funnel)

한 번만 설정하면 이후로는 `docker/run.sh`만 띄우면 자동으로 원격 접속이 열린다.

```bash
# 최초 1회 — 디바이스에 Tailscale 설치 + 로그인
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up                     # 뜨는 URL을 폰/PC로 열어 로그인

# 필요할 때만 — 공개 URL 켜기/끄기 (둘 다 sudo 비밀번호 필요, SSH로 직접 실행)
sudo tailscale funnel --bg 8080
sudo tailscale funnel --https=443 off   # 다 보여준 뒤 반드시 끌 것
```

접속(외부): `https://<기기이름>.<tailnet>.ts.net/app` — 실제 주소는 기기에서 `tailscale status`로 확인(공개 리포라 적지 않는다)
접속(Tailscale 기기끼리, Funnel 없이): UNO Q의 Tailscale IP로 직접 (`tailscale ip -4`로 확인)

> **이 앱은 PIN(기본 `1234`) 하나 말고 실질적 인증이 없다.** Funnel이 켜진 동안엔 그
> 링크를 아는 누구나 카메라·PTZ·경비모드 사진을 볼 수 있다 — 데모 보여줄 때만
> 켰다 끄는 용도로 쓸 것, 상시 노출 금지.
>
> **뷰어(스트림 접속자)가 늘수록 FPS가 떨어진다** — 뷰어 0명 ~11.3 FPS, 1명 ~10,
> 2명 동시 접속(예: PC+폰) ~8까지 하락(실측). 파이썬 GIL 스레드 경합 + (원격이면)
> 암호화 오버헤드가 원인. 완화하려면 `--jpeg-quality`를 낮추는 정도가 현실적.

### 3.3 개발 PC — 서보 직결 테스트

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

### 3.4 모델 준비 — 보통 불필요

`models/movenet_thunder_int8.tflite`(7.1 MB)는 **리포에 커밋되어 있다.** clone하면 바로 있다.
자매 리포에서 모델을 갱신할 때만 아래를 쓴다.

```bash
bash scripts/copy_model.sh    # ../unoq-companion-robot/pose/models/ -> models/
```

---

## 4. 폴더 구조

```
health_care_bot/
├── README.md                   (본 문서 — 진입점)
├── APP_GUIDE.md                React 시절 실행 가이드 (일부 낡음)
├── APP_PLAN.md                 초기 앱 기획서 (07-08, 데이터 계약의 출처)
├── health_care_bot_mvp_screen_plan.md   MVP 화면 기획 (07-11)
├── app_reference.png           앱 레퍼런스 스크린샷
├── src/                        런타임 (컨테이너가 실행)
│   ├── main.py                 통합 진입점: 루프 + CLI + 텔레메트리
│   ├── pose_utils.py           keypoint 상수 / letterbox / 중심점 헬퍼 / draw
│   ├── angles.py               knee_angle, shoulder_elev_angle, pick_angle
│   ├── exercise_counter.py     RepCounter + Squat/OverheadPress/LateralRaise
│   ├── ptz_controller.py       PTZ 추적 + 손실 복구 + 서보 직결
│   ├── st3215_bus.py           ST3215 프로토콜 저수준 드라이버
│   ├── http_server.py          MJPEG + stats.json + /api/* + /app + /captures/* 서빙
│   ├── app_state.py            세션 상태 + 운영자 PIN 제어권 lock + 경비 모드 상태
│   └── guard_capture.py        경비 모드: 사람 감지 판정 + JPEG 저장 + 로그
├── captures/                    경비 모드 촬영 산출물 (jpg + guard_log.jsonl) — gitignore 대상
├── web/
│   ├── app/index.html          ★ /app으로 서빙되는 애플 "Fluid" 정적 페이지 — **확정 UI**
│   │                             자체포함 단일 파일(48 KB). 빌드 대상이 아니고 여기를 직접 고친다
│   ├── src/                    Vite + React PWA 시안 6종 — 보관 계층, 서빙 안 함
│   ├── dist/                   위 시안의 빌드 산출물 — gitignore. **없어도 /app은 정상**
│   ├── ARCHITECTURE.md         웹 설계 근거 ("왜 이렇게")
│   └── DESIGN.md               시안·서체·색 결정 근거 (07-21 기준, 일부 오래됨)
├── design_demos/               독립 HTML 시안 2종 (Fluid 원본 / Field Optics)
├── docker/
│   ├── Dockerfile              Ubuntu 22.04 + python3.10 + ai-edge-litert + pyserial
│   ├── requirements.txt
│   └── run.sh                  빌드 + 실행 (카메라/시리얼 노드 자동 탐색, tty 유무 감지, PITCH_SIGN/YAW_SIGN 지원)
├── models/movenet_thunder_int8.tflite
├── scripts/                    벤치·도구 (런타임 아님)
│   ├── calibrate_st3215.py     중앙 재캘리브레이션 / 긴급정지
│   ├── test_st3215_serial.py   ping/read/move/sweep/set-id/dual-spin
│   ├── ptz_camera_track.py     PTZ 단독 테스트 (작업본, v1/v2 백업 동봉)
│   ├── mock_serve.py           카메라·모델 없이 API/프론트만 검증 (실기 아님)
│   └── copy_model.sh
├── ptz/sketch/                 MCU 스케치 — 현재 미사용 (MCU 트랙 보류)
├── 3d_model/                   짐벌 하우징 3D 모델
│   ├── source/ · 3mf/ · stl/   생성 스크립트 / 출력용 / 메시
│   └── validation/ · preview/  간섭 검증 스키마 / 미리보기
├── docs/                       ← 아래 §5
└── backup/                     복원점 5개 (pre_web_integration 등)
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
| — | [`docs/history/2026-09-09_01`](docs/history/2026-09-09_01_repo_clonability_fixed_deploy_ui_committed.md) | **가장 최신** — 배포 UI를 `web/app/`으로 커밋, Dockerfile CMD·mock_serve 수정 |
| — | [`docs/history/2026-08-08_01_session_handoff.md`](docs/history/2026-08-08_01_session_handoff.md) | 실기 맥락 — 경비 모드, PTZ 버그 3건, Tailscale 원격접속 |
| — | [`web/ARCHITECTURE.md`](web/ARCHITECTURE.md) · [`APP_GUIDE.md`](APP_GUIDE.md) | 웹앱 설계 근거 / React 시절 실행 가이드(일부 낡음) |
| — | [`donghee-ai/unoq-edge-ai-lines`](https://github.com/donghee-ai/unoq-edge-ai-lines) | **자매 리포**(private) — Vision/ASR/Pose/KWS 4 라인 PoC + 실측. 본 라인의 모델 출처 |

---

## 6. CLI 옵션 (자주 쓰는 것)

전체는 `python3 src/main.py --help`.

| 플래그 | 기본 | 의미 |
|---|---|---|
| `--mode` | `squat` | `squat` / `overhead` / `lateral` / `guard`. 웹 `/api/mode`로 실시간 변경됨 |
| `--camera` | `0` | `/dev/videoN` 인덱스 |
| `--serial` | (없음) | 서보 버스 포트. **미지정 시 PTZ disabled**로 degrade |
| `--pitch-sign` / `--yaw-sign` | `-1` / `1` | 짐벌 재조립 후 방향 반전 보정 (2026-08-06 확정값). `docker/run.sh`는 `PITCH_SIGN`/`YAW_SIGN` 환경변수로 노출 |
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
- **HTTP는 인증이 없다.** 운영자 mutation만 PIN 기반 제어권 lock으로 막혀 있고
  조회·스트림은 무인증이다. **로컬 LAN 외부 노출 금지.** 기본 PIN은 `1234`이고
  **코드 수정 없이 `HCB_OPERATOR_PIN` 환경변수로 바꾼다**(`docker/run.sh`가 컨테이너로
  전달한다). 시연 전 교체 권장:
  `HCB_OPERATOR_PIN=8317 bash docker/run.sh`
  바꾸면 `/app`이 접속 시 PIN을 한 번 물어보고 브라우저에 기억한다(기본값이면 안 묻는다). **Tailscale Funnel(§3.2)도 이 규칙에서 예외가 아니다** —
  켜져 있는 동안엔 인터넷 전체에 무인증으로 노출되는 것과 같으니 데모 끝나면
  반드시 끌 것.
- **UNO Q는 USB 호스트 VBUS가 꺼져 있다** — 버스파워 허브/장치는 인식되지 않는다.
  **셀프파워(외부전원) USB 허브 필수.** 카메라·서보가 *둘 다* 안 잡히면 개별 장치가
  아니라 허브 전원부터 의심할 것.

---

## 8. 자주 밟는 함정

| 함정 | 요약 | 상세 |
|---|---|---|
| 디바이스 노드 번호 | `/dev/videoN`·`ttyACM/ttyUSB`가 부팅마다 바뀐다. 번호를 규칙으로 적지 말고 **이름으로 식별** | [issues/2026-07-19_01](docs/issues/2026-07-19_01_device_node_names_are_not_stable.md) |
| argparse ↔ run.sh 동기화 | `--mode` choices를 바꾸면 `run.sh`(및 Dockerfile CMD)의 하드코딩 인자도 같이 고쳐야 한다. `--rm`이라 `docker logs`에 안 남음 | [history/2026-07-26_02](docs/history/2026-07-26_02_pushup_removed_overhead_lateral_added.md) |
| ~~`npm run build`가 Fluid를 덮음~~ | **해소(2026-09-09).** 배포본을 `web/app/`으로 분리하고 서버가 `web/app` → `web/dist` 순으로 찾게 했다. 빌드해도 `/app`은 그대로 | [docs/05](docs/05_web_ui_fluid.md) §9-1 |
| 폰 접속 실패 | `ERR_ADDRESS_UNREACHABLE` = 폰 **랜덤 MAC**(서버 문제 아님) | [issues/2026-07-26_01](docs/issues/2026-07-26_01_mobile_web_access_fails_random_mac.md) |
| `cv2.CAP_PROP_BUFFERSIZE` | 드라이버가 무시한다. `FrameGrabber`(최신 프레임만 유지)로 해결됨 | [issues/2026-07-11_04](docs/issues/2026-07-11_04_camera_buffer_accumulation_causes_growing_latency.md) |
| `adb push` | Git Bash는 경로를 변환해 조용히 실패 → **PowerShell로**. 디렉토리는 remote `rm -rf` 먼저(안 하면 `src/src/` 중첩) | [issues/2026-07-11_01](docs/issues/2026-07-11_01_adb_push_msys_path_mangling.md), [_02](docs/issues/2026-07-11_02_adb_push_directory_nests_when_remote_exists.md) |
| cp949 콘솔 크래시 | em-dash·⚠ 같은 문자를 **코드/주석**에 쓰면 Windows 콘솔에서 `UnicodeEncodeError` | [docs/08](docs/08_troubleshooting.md) §7 |
| 프론트에서 API 주소 포트 하드코딩 | `location.hostname:8080`처럼 고정하면 리버스 프록시/터널(Tailscale Funnel 등, 외부 포트가 8080이 아님)에서 스트림·상태 요청이 전부 실패. `location.origin`을 그대로 쓸 것 | [history/2026-08-08_01](docs/history/2026-08-08_01_session_handoff.md) §3 |
| 모바일 접속 QR을 정적 이미지로 생성 | IP가 DHCP라 바뀌는데 QR을 미리 렌더링해두면 절대 안 갱신됨. 브라우저에서 매번 `location`으로 다시 인코딩할 것(`qrSvg()`) | [history/2026-08-08_01](docs/history/2026-08-08_01_session_handoff.md) §3 |
| `docker/run.sh`가 tty 없는 세션에서 조용히 죽음 | `-it` 고정이라 비대화형 SSH 등에서 `the input device is not a TTY`로 즉시 종료(`--rm`이라 로그도 안 남음). tty 유무를 감지해 조건부로 적용하도록 수정됨 | [history/2026-08-08_01](docs/history/2026-08-08_01_session_handoff.md) §3 |
| "PC는 되는데 폰만 안 됨"이 무선 격리를 배제하는 근거가 아님 | PC가 실제로 유선으로 나가고 있으면 무선 클라이언트 격리를 애초에 안 타는 것. `Find-NetRoute`(Windows)로 실제 경로 먼저 확인 | [history/2026-08-08_01](docs/history/2026-08-08_01_session_handoff.md) §3 |
| 자동 트리거와 수동 트리거가 같은 쿨다운 공유 | 경비모드 "직접 촬영" 버튼이 자동감지 쿨다운을 공유해서, 사람이 계속 화면에 있으면 버튼이 조용히 씹힘. 수동 트리거는 쿨다운 무시하고 항상 즉시 반응하게 분리 | [history/2026-08-08_01](docs/history/2026-08-08_01_session_handoff.md) §3 |
| Docker 이미지가 ROOT 파티션을 채움 | `/var/lib/docker`가 ROOT에 있어 재빌드를 반복하면 옛 레이어가 안 쓰는 채로 계속 쌓인다. `docker image prune -a`로 회수 가능(단, 다른 프로젝트 이미지까지 같이 지워질 수 있으니 목록 확인 후) | [history/2026-08-08_01](docs/history/2026-08-08_01_session_handoff.md) |

전체 목록은 [`docs/08_troubleshooting.md`](docs/08_troubleshooting.md) — 증상에서 원인으로
가는 색인 + `issues/` 전체 목록이 있다.

---

## 9. 성능 (실측)

| 항목 | 값 | 비고 |
|---|---|---|
| 추론 FPS | ~11.4 | **invoke(추론) 바운드**. 인코딩 on/off 차이 ~0(뷰어 0명 기준) |
| 루프 지연 | ~90 ms | grab → invoke → draw → encode 직렬 |
| 동시 뷰어 1명 | ~10 FPS | 스트림 배달 스레드 1개 추가 시 GIL 경합으로 하락 (로컬/원격 무관) |
| 동시 뷰어 2명(예: PC+폰) | ~8 FPS | 스레드 경합 + 원격이면 Tailscale 암호화 오버헤드까지 겹침 |
| CPU | ~83% (4코어 합산 100% 기준) | 이미 warning 구간, 여유 17% |
| CPU 클럭 | 2016 MHz 전 코어 = 최대 | 거버너로 더 올릴 여지 없음 |
| 온도 | 51~73°C | throttle 전 |

FPS를 올리는 유일한 큰 레버는 **NPU/DSP 델리게이트**(Hexagon HTP · QNN/LiteRT)다 —
이 CPU에는 `asimddp`(INT8 dotprod)가 없어 INT8 고속 커널을 못 쓴다. 근거와 착수 지점:
[`docs/history/2026-07-21_02`](docs/history/2026-07-21_02_session_handoff.md) §4.

---

## 10. 모델 / 제3자 자산

> 이 리포 자체의 라이센스는 **아직 정하지 않았다.** LICENSE 파일이 없는 동안에는
> 저작권이 저자에게 유보된다(재배포·상업적 이용에 대한 허가 없음).

- 추론 모델: **MoveNet Thunder INT8** (`models/movenet_thunder_int8.tflite`, 7.1 MB) —
  기존 pose 라인 자산 재사용. **git에 포함되어 있어 clone하면 바로 쓸 수 있다**
  (갱신할 때만 `scripts/copy_model.sh`).
- 서체(Pretendard·Gabarito)는 **SIL OFL 1.1**이고, OFL이 요구하는 라이선스 사본을
  `web/public/fonts/licenses/`에 동봉했다.

**재배포하는 남의 저작물 전체 목록과 요구 표기는 [`THIRD_PARTY.md`](THIRD_PARTY.md).**
MoveNet의 CC BY 4.0 저작자 표시, 서체 OFL 표기, 벤더 CAD를 왜 뺐는지가 거기 있다.