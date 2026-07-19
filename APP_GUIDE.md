# Health Care Bot Live — 실행 가이드 & 구조

`APP_PLAN.md`(및 화면 분리형 개정판) 기반으로 만든 모바일 웹 앱(PWA)의 실행
방법과 코드 구조를 정리한 문서. 로봇 자체(추론 루프, PTZ 하드웨어)는
`README.md`를 참고하고, 본 문서는 **웹 앱 계층**(`web/` + `src/`에 추가된
API)만 다룬다. "왜 이렇게 만들었나"는 [`web/ARCHITECTURE.md`](web/ARCHITECTURE.md),
의사결정/이슈 히스토리는 [`docs/history/`](docs/history/) ·
[`docs/issues/`](docs/issues/) 참고.

## 1. 한눈에 보는 구조

```
health_care_bot/
├── src/                      # 백엔드 (Python, 기존 추론 루프 + 신규 앱 API)
│   ├── main.py                 추론 루프 진입점 — app_state를 http_server에 연결
│   ├── http_server.py          GET /, /stream.mjpg, /stats.json, /app/*
│   │                           POST /api/ptz, /api/mode, /api/session/*, /api/control/*
│   ├── app_state.py            세션(운동) 상태 + 운영자 PIN 제어권 lock  ← 신규
│   ├── ptz_controller.py       자동 추적 + manual_pan/tilt/center       ← 수정
│   ├── exercise_counter.py     스쿼트/푸시업 rep 카운터 (기존)
│   ├── angles.py / pose_utils.py  각도 계산 / keypoint 유틸 (기존)
│   └── __init__.py             (main.py에 get_cpu_temp_c() 추가 — CPU 온도, 없으면 None)
├── web/                      # 프론트엔드 (Vite + React + TypeScript, PWA)  ← 신규
│   ├── ARCHITECTURE.md        "왜 이렇게 만들었나" — 설계 근거 문서
│   ├── src/
│   │   ├── App.tsx              role 파싱 + 탭 상태 + 상단 헤더(테마 토글 포함) + 네비게이션
│   │   ├── api.ts               백엔드 fetch 래퍼 (client_id 자동 첨부)
│   │   ├── types.ts             stats.json / API 응답 TS 타입
│   │   ├── hooks/
│   │   │   ├── useStats.ts          /stats.json 500ms polling + 연결 상태 판정
│   │   │   ├── useOperatorControl.ts PIN 제어권 claim/heartbeat/해제
│   │   │   ├── useMediaQuery.ts     데스크톱(≥900px) 여부
│   │   │   └── useTheme.ts          Dragonwing(기본)/Reference 테마 전환, localStorage 저장
│   │   ├── screens/
│   │   │   ├── LiveScreen.tsx       라이브 카메라 + 카운트 + 자세 피드백
│   │   │   │                       (FPS/지연/CPU온도/RAM 카드는 데스크톱에서만, 모바일엔 숨김)
│   │   │   ├── ExerciseScreen.tsx   모드 선택 + 세션 진행/결과
│   │   │   ├── CameraControlScreen.tsx  PTZ 조작 (운영자 전용)
│   │   │   └── MoreScreen.tsx       장비상태(전체 텔레메트리)/QR/카메라설정/운동인식설정/앱정보 메뉴
│   │   ├── components/          LiveCamera, PtzPad, ProgressRing, PinModal, QrPanel, InfoRow,
│   │   │                       ThemeToggle, NavBar 등
│   │   └── lib/feedback.ts      각도 기반 실시간 자세 피드백 문구 생성
│   ├── dist/                  `npm run build` 산출물 — 백엔드가 `/app`에서 그대로 서빙
│   └── vite.config.ts         base: '/app/', dev 서버 프록시 설정
├── scripts/
│   └── mock_serve.py         카메라/모델 없이 프론트만 검증할 때 쓰는 목업 백엔드 ← 신규
├── docs/{history,issues}/    의사결정/문제 실시간 기록 (1 사건 1 파일)
└── APP_PLAN.md / health_care_bot_mvp_screen_plan.md   기획 문서 (원본)
```

**핵심 원칙**: 프론트는 정적 파일로 빌드되어 백엔드(`http_server.py`)가 직접
서빙한다. 별도 Node 서버가 배포에 필요 없다 — UNO Q에는 Python 프로세스
하나만 떠 있으면 된다.

## 2. 실행 방법

### 2.1 실기(UNO Q) 배포 — 실제 시연용

```bash
# 최초 1회: 프론트 빌드
cd web
npm install
npm run build          # → web/dist/ 생성

# 백엔드 실행 (컨테이너 안 또는 로컬)
cd ..
python3 src/main.py \
    models/movenet_thunder_int8.tflite \
    --mode auto --camera 0 --serial /dev/ttyACM0 --serve 8080
```

접속 URL:

| 대상 | URL |
|---|---|
| 관람객(viewer) | `http://<UNO_Q_IP>:8080/app` |
| 운영자(operator) | `http://<UNO_Q_IP>:8080/app?role=operator` |
| 디버그 페이지(기존) | `http://<UNO_Q_IP>:8080/` |

운영자 PIN 기본값은 `1234` (`src/app_state.py`의 `_operator_pin`). 실제
시연 전에 반드시 바꿀 것.

`web/dist`가 없는 상태로 `/app`에 접속하면 백엔드가 503 + 안내 JSON
(`"hint": "cd web && npm install && npm run build"`)을 반환한다.

### 2.2 프론트만 따로 개발할 때 (`npm run dev`)

카메라/모델 없이 UI만 빠르게 고칠 때는 Vite dev 서버 + 목업 백엔드 조합을
쓴다.

```bash
# 터미널 1 — 목업 백엔드 (카메라/서보 없이 stats.json/API만 흉내)
python scripts/mock_serve.py          # http://localhost:8090

# 터미널 2 — 프론트 dev 서버 (HMR)
cd web
VITE_BACKEND_URL=http://localhost:8090 npm run dev   # http://localhost:5173
```

`vite.config.ts`가 `/stats.json`, `/stream.mjpg`, `/api/*`를
`VITE_BACKEND_URL`(기본 `http://localhost:8080`)로 프록시하므로 CORS 신경
쓸 필요 없이 `http://localhost:5173/?role=operator`로 바로 접속해 개발하면
된다.

실제 UNO Q가 켜져 있고 같은 네트워크라면 `VITE_BACKEND_URL`을 그 기기의
`http://<UNO_Q_IP>:8080`으로 바꿔서 진짜 카메라 스트림을 보며 개발할 수도
있다.

### 2.3 프론트 수정 후 실기에 반영하기

```bash
cd web && npm run build
```

만으로 끝난다 — `web/dist`만 갱신되면 백엔드 재시작 없이 바로 `/app` 새로고침 시 반영된다 (Python 프로세스는 그대로 두어도 됨).

## 3. 역할(role) & 권한 모델

- URL의 `?role=operator` 유무로 화면에 운영자 전용 탭(카메라 제어)과 버튼을
  보여줄지만 결정한다. **실제 권한 검사는 서버가 한다** — role 파라미터는
  UI 노출 여부일 뿐, 서버 mutation API(`/api/ptz`, `/api/session/*`,
  `/api/mode`)는 전부 `client_id` + 제어권 lock을 확인한다.
- 운영자가 PTZ나 세션을 처음 조작하면 `PinModal`이 뜨고, PIN이 맞으면
  `POST /api/control/claim`으로 60초 lock을 얻는다. 이후 20초마다
  `POST /api/control/heartbeat`로 자동 연장한다 (`useOperatorControl.ts`).
- 다른 기기가 이미 lock을 쥐고 있으면 배지가 "다른 기기가 제어 중"으로
  바뀌고 버튼이 비활성화된다 (`app_state.py::claim_control`의
  `locked_by_other`).

## 4. API 요약

| Method | Path | 설명 | 인증 |
|---|---|---|---|
| GET | `/stats.json` | 추론 상태 + `app.session` / `app.control` / `viewer_count` | 없음 |
| GET | `/stream.mjpg` | MJPEG 라이브 스트림 | 없음 |
| GET | `/app/*` | 빌드된 React 앱 정적 파일 | 없음 |
| POST | `/api/control/claim` | `{client_id, pin}` → 제어권 획득 | PIN |
| POST | `/api/control/heartbeat` | 제어권 60초 연장 | lock 보유자만 |
| POST | `/api/control/release` | 제어권 반납 | lock 보유자만 |
| POST | `/api/ptz` | `{command: pan\|tilt\|center\|auto_track\|stop, delta_deg?}` | lock 필요 |
| POST | `/api/mode` | `{mode: auto\|squat\|pushup}` | lock 필요 |
| POST | `/api/session/start` \| `/pause` \| `/resume` \| `/reset` \| `/finish` | 세션 상태 전이 | lock 필요 |

모든 POST 요청 body에는 `client_id`가 필요하며, `web/src/api.ts`가
`localStorage`에 저장된 client_id를 자동으로 붙인다.

`stats.json`에는 `cpu_temp_c`(SoC 온도, `/sys/class/thermal/thermal_zone0/temp`
읽기 — 없는 환경/Windows에서는 `null`)도 포함된다. 앱에서는 더보기 →
장비 상태, 그리고 데스크톱 화면의 라이브 텔레메트리 카드에서 쓴다.

## 5. 트러블슈팅

| 증상 | 원인 / 조치 |
|---|---|
| `/app` 접속 시 503 `web_not_built` | `cd web && npm run build` 후 재접속 (백엔드 재시작 불필요) |
| PTZ/세션 버튼이 계속 비활성 | 운영자 PIN을 아직 입력 안 했거나 다른 기기가 lock 보유 중 — 상단 배지 확인 |
| 스트림이 "재연결 중"에서 멈춤 | 백엔드(`--serve` 포트)가 실행 중인지, `/stream.mjpg`가 직접 열리는지 확인 |
| dev 서버에서 상태가 안 뜸 | `VITE_BACKEND_URL`이 실제 백엔드(또는 `mock_serve.py`) 주소를 가리키는지 확인 |
| Windows에서 `mock_serve.py` 실행 시 `ModuleNotFoundError: No module named 'cv2'` | conda `(base)` 등 cv2 없는 Python이 잡힌 것. `cv2`가 설치된 인터프리터를 직접 지정해서 실행 (예: `& "C:\...\Python314\python.exe" scripts/mock_serve.py`) 하거나 `pip install opencv-python numpy` |
| Git Bash에서 `adb push`가 "성공" 로그를 내고도 디바이스에 실제로 반영 안 됨 | MSYS가 리모트 경로(`/home/arduino/...`)를 Windows 경로로 잘못 변환하는 문제. **PowerShell로 adb 명령 실행** — 상세: [`docs/issues/2026-07-11_01_adb_push_msys_path_mangling.md`](docs/issues/2026-07-11_01_adb_push_msys_path_mangling.md) |
| `web/dist`를 다시 push했는데 반영이 안 됨 | remote `web/dist`가 이미 있으면 `adb push`가 안에 `web/dist/dist/`로 중첩시킨다. `adb shell "rm -rf .../web/dist"` 먼저 실행 후 push — 상세: [`docs/issues/2026-07-11_02_adb_push_directory_nests_when_remote_exists.md`](docs/issues/2026-07-11_02_adb_push_directory_nests_when_remote_exists.md) |
