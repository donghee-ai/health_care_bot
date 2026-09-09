# 실행 · 배포 런북

본 문서는 로봇을 **띄우고 내리고 코드를 밀어넣는** 절차를 순서대로 정리합니다. 매 세션
실행 전에 확인해야 하는 것(노드 번호, 전원)과 환경별 함정을 함께 담습니다.

증상별 진단은 [`08_troubleshooting.md`](08_troubleshooting.md).
하드웨어 캘리브레이션은 [`06_hardware_calibration.md`](06_hardware_calibration.md).

## 0. 한 눈에

```bash
# 디바이스에서 (평소 이 한 줄)
ssh arduino@192.168.0.50
cd ~/health_care_bot && bash docker/run.sh

# 접속
http://192.168.0.50:8080/app

# 내리기
docker stop health-care-bot
```

## 1. 디바이스 접속

| 항목 | 값 |
|---|---|
| 호스트 | `unoq-korea01` / 사용자 `arduino` |
| IP | `192.168.0.50` (DHCP — 바뀌면 `adb shell "hostname -I"`로 재확인) |
| Tailscale | 설치돼 있음. 실제 주소는 기기에서 `tailscale ip -4` / `tailscale status`로 확인 (§8) |
| 앱 루트 | `/home/arduino/health_care_bot` (git 저장소 아님 — 파일 복사 배포) |
| 런타임 | Docker 컨테이너 `health-care-bot:22.04` |
| adb serial | `& $ADB devices`로 확인 (기기 고유값이라 문서에 적지 않는다) |

**SSH가 기본이다** (2026-07-19에 키 등록 완료 — 비번 없이 붙는다).

```powershell
ssh arduino@192.168.0.50
```

> **SSH는 네트워크로 붙으므로 PC-USB 연결이 필요 없다.** adb를 쓰려고 USB-C를 물고 있으면
> 그 포트에 허브+카메라를 못 꽂는다. SSH로 작업하면 USB-C를 비워 카메라를 연결할 수 있다.
> 단 UNO Q가 그 포트로 **전원**을 받고 있지 않은지 먼저 확인할 것.

**adb (USB 연결 시):**

```powershell
$ADB = "$env:LOCALAPPDATA\Arduino15\packages\arduino\tools\adb\32.0.0\adb.exe"
& $ADB devices
```

## 2. 실행 전 확인 — 노드 번호는 고정이 아니다

USB를 어느 포트에 꽂았는지, 어떤 순서로 꽂았는지, 부팅 시점에 무엇이 연결돼 있었는지에 따라
**매번 바뀐다.** 문서에 적힌 번호를 그대로 쓰지 말고 실행 직전에 확인할 것.

```bash
v4l2-ctl --list-devices          # 카메라 노드 — "USB ... Camera"로 표시된 쪽이 진짜
ls /dev/ttyACM* /dev/ttyUSB*     # 서보 어댑터 노드 (양쪽 다 볼 것)
```

`v4l2-ctl`이 없으면:

```bash
for v in /sys/class/video4linux/video*; do echo "$(basename $v) $(cat $v/name)"; done
```

**카메라** — Venus 코덱(디코더/인코더)과 USB 카메라가 `/dev/video*`를 나눠 갖는데 **순서가
부팅마다 뒤바뀐다.** `Qualcomm Venus`로 표시된 노드를 지정하면 컨테이너가 카메라를 못 열고
즉시 종료된다.

| 관측 시점 | USB 카메라 | Venus 코덱 |
|---|---|---|
| 2026-07-11 | (연결 없음) | video0·1 |
| 2026-07-19 | video0·1 | video2·3 |
| 2026-07-26 | **video2** | (나머지) |
| **2026-09-08** | **video0·1** | video2(encoder)·3(decoder) |

2026-07-26과 2026-09-08이 정확히 반대다. **표를 규칙으로 읽지 말 것** — 이 표는 "번호가
실제로 뒤집힌다"는 증거이지 조회표가 아니다. `run.sh`의 이름 기반 자동 탐색에 맡기는 게
정답이다(2026-09-08 실기: `camera : /dev/video0 (--camera 0)`으로 정상 선택됨).

**서보 어댑터(CH343)** — 커널/드라이버에 따라 `ttyACM`으로도 `ttyUSB`로도 잡힌다. UNO Q는
CDC-ACM이라 **`/dev/ttyACM0`**.

> 번호를 규칙으로 외우지 말 것. "video2 이상이 진짜 카메라"라는 옛 규칙은 실측으로 반박됐다:
> [`issues/2026-07-19_01`](issues/2026-07-19_01_device_node_names_are_not_stable.md)

## 3. 디바이스 실행

```bash
cd ~/health_care_bot
bash docker/run.sh                  # 노드 자동 탐색 + 기동 (foreground)
CAMERA_DEV=/dev/video2 bash docker/run.sh    # 수동 지정
bash docker/run.sh --rebuild        # 이미지 강제 재빌드
bash docker/run.sh --shell          # 디버그 셸로 진입
```

접속:

| 대상 | URL |
|---|---|
| 웹앱 (뷰어=운영자, 공유 제어권) | `http://192.168.0.50:8080/app` |
| 디버그 페이지 (스트림 + 원본 stats) | `http://192.168.0.50:8080/` |

### 3-1. `run.sh`가 해주는 것

1. 이미지가 없으면 빌드
2. **카메라 노드 자동 탐색** — `/sys/class/video4linux/*/name`에서 이름에 `Camera`가 든
   노드 선택(Venus 회피). 미검출 시 `/dev/video2` 폴백
3. **시리얼 노드 자동 탐색** — `/dev/ttyACM*` → `/dev/ttyUSB*` 순
4. `--net host`, `-v $PWD:/work`, 찾은 노드만 `--device`로 전달
5. 노드가 없으면 눈에 띄는 경고 블록 출력

### 3-2. 기동 로그에서 반드시 볼 것

```
  camera : /dev/video0 (--camera 0)
  serial : /dev/ttyACM0            ← (MISSING — PTZ disabled)면 PTZ가 조용히 꺼진다
  sign   : yaw=1 pitch=-1          ← pitch 부호(06 §0). 뒤집혀 있으면 위아래가 반대로 돈다
  actual : 640x480                 ← 카메라가 실제로 열렸는지
  [ptz] 버스 연결 ... 중앙(180/180) 정렬 후 시작
```

**PTZ disabled는 한 줄 경고 뒤 정상 실행이 계속된다** — "PTZ만 왜 안 되지"로 헤매기 전에 이
줄을 먼저 볼 것. degrade 규칙 전체: [`01_architecture.md`](01_architecture.md) §6.

### 3-3. 기동 실패를 조사할 때

`run.sh`는 `--rm`으로 컨테이너를 띄우기 때문에 **죽으면 `docker logs`에 아무것도 안 남는다.**

```bash
bash docker/run.sh > /tmp/hcb_run.log 2>&1     # 캡처해서 원인 확인
```

`run.sh`는 `-it`라 비대화형 SSH에서는 안 붙는다. 백그라운드로 오래 돌릴 때는 `screen`
세션(관례상 이름 `hcb`)을 쓰거나 `docker run -d`로 직접 띄운다.

### 3-4. 중지

```bash
docker stop health-care-bot
```

> **세션을 끝낼 때 꼭 내릴 것.** 켜둔 채 두면 카메라 ON + 서보 torque ON 상태가 유지된다.

## 4. 개발 PC 실행

```powershell
cd C:\Project\health_care_bot

# 통합 실행 (웹앱 + 카운팅 + PTZ)
py -3.14 src/main.py models/movenet_thunder_int8.tflite --camera 0 --serial COM9 --serve 8080
#   http://localhost:8080/app

# PTZ 추적만 단독 테스트 (OpenCV 창, q=종료 r=카운트리셋)
py -3.14 scripts/ptz_camera_track.py --port COM9 --camera 0 --drive
```

### 4-1. PC 환경 함정 4가지 (매번 걸림)

1. **반드시 `py -3.14`** — 이 PC엔 파이썬이 둘이고 아나콘다 `base`엔 `cv2`가 없다. 필요한
   패키지(cv2/numpy/pyserial/ai-edge-litert)는 Python 3.14에만 있다.
2. **카메라 인덱스가 USB 재연결마다 뒤바뀐다.** 헷갈리면 각 인덱스에서 한 장 캡처해 눈으로
   확인할 것.
3. **서보 전원(6~12.6V)은 USB와 별개다.** 전원이 없으면 포트는 정상으로 열리는데 ID가 전부
   무응답이 된다 → COM 포트/ID 문제로 오해하기 쉽다. **어댑터 배럴잭을 먼저 확인.**
4. 서보 포트는 **COM9** (USB-Enhanced-SERIAL CH343), baud 1,000,000.

> PC와 실기는 FPS가 다르다(29 vs 11). 추적 각속도는 같지만 **관성 지속만 프레임 수 기준**이라
> PC에서 2.6배 짧게 보인다 — 동작을 비교할 때 혼동 주의
> ([`03`](03_algorithm_ptz_tracking.md) §12).

## 5. 코드 배포 (PC → 디바이스)

### 5-1. SSH (권장)

```bash
tar -czf - src | ssh arduino@192.168.0.50 'cd ~/health_care_bot && rm -rf src && tar -xzf -'
```

### 5-2. adb (USB 연결 시) — 순서가 정해져 있다

```powershell
$APP = "/home/arduino/health_care_bot"
& $ADB shell "rm -rf $APP/src"            # 먼저 지운다 (안 지우면 src/src/로 중첩)
& $ADB push src "$APP/src"
& $ADB shell "cd $APP; md5sum src/*.py"   # push 로그를 믿지 말고 해시 대조
```

**함정 2건**이 이 순서를 만들었다:

- **Git Bash로 adb를 쓰면 안 된다** — MSYS가 리모트 경로를 Windows 경로로 잘못 변환해 push가
  조용히 실패한다. **PowerShell로 실행**
  ([`issues/2026-07-11_01`](issues/2026-07-11_01_adb_push_msys_path_mangling.md)).
- **디렉토리 push 전 remote를 `rm -rf`** — remote 경로가 이미 있으면 `adb push`가 그 안에
  `src/src/`로 중첩시킨다. 구버전이 그대로 서빙돼 "반영 안 됨"으로 보인다
  ([`issues/2026-07-11_02`](issues/2026-07-11_02_adb_push_directory_nests_when_remote_exists.md)).

> **SSH 세션 안에서 PC용 명령을 실행하지 말 것.** SSH로 들어간 뒤 PowerShell 문법(`$var = ...`)을
> 붙여넣으면 bash `syntax error`가 난다. 더 나쁜 건 `ssh arduino@...`를 또 실행해 **자기
> 자신에게 재접속**하는 것이다. 프롬프트가 `arduino@unoq-korea01:~$`인지 먼저 볼 것.

## 6. 웹 재배포

```bash
# 배포본은 자체포함 단일 파일(48 KB)이라 이것 하나만 올리면 된다
scp web/app/index.html arduino@192.168.0.50:~/health_care_bot/web/app/index.html
```

디바이스를 git으로 관리한다면 `git pull`만으로도 반영된다 — 배포본이 커밋되기 때문이다.

`http_server`가 매 요청마다 디스크에서 읽으므로 **컨테이너 재시작이 필요 없다.**

> **`npm run build`는 더 이상 `/app`을 덮지 않는다**(2026-09-09). 서버가
> `web/app` → `web/dist` 순으로 찾기 때문이다. [`05_web_ui_fluid.md`](05_web_ui_fluid.md) §9-1.

## 7. 프론트만 따로 개발할 때

**확정 UI인 Fluid는 빌드가 없다.** `web/app/index.html` 한 파일을 고치는 것이 전부이고,
가장 빠른 확인 경로는 실기에 올려 브라우저를 새로고침하는 것이다(§6 — 컨테이너 재시작 불필요).

로봇 없이 UI만 보려면 목업 백엔드를 쓴다. `mock_serve.py`는 `/app`도 같이 서빙하므로
**React 없이 Fluid를 그대로 열 수 있다**:

```bash
python scripts/mock_serve.py     # http://localhost:8090/app  ← Fluid가 그대로 뜬다
```

> `mock_serve.py`는 2026-07-26 pushup 제거 이후 `PushupCounter`를 import해 실행 즉시
> `ImportError`가 났었다. **2026-09-09에 현재 카운터 3종으로 고쳤고 기동을 확인했다.**

**보관된 React 계층**(`web/src/`)을 볼 때만 Vite를 쓴다. 이건 정상 작업 흐름이 아니다:

```bash
cd web && VITE_BACKEND_URL=http://localhost:8090 npm run dev   # http://localhost:5173
```

`npm run build`의 산출물은 `web/dist/`이고 `/app/assets/*`로만 노출된다. 확정 UI인
`web/app/index.html`은 건드리지 않는다. [`05_web_ui_fluid.md`](05_web_ui_fluid.md) §9-1.

## 8. 원격 접속 — 같은 Wi-Fi가 아닐 때 (Tailscale Funnel)

로봇 Wi-Fi에 붙을 수 없는 곳(다른 망, 모바일 데이터)에서 `/app`을 열어야 할 때 쓴다.

```bash
# 최초 1회
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up                       # 출력되는 URL을 폰/PC로 열어 로그인

# 보여줄 때만
sudo tailscale funnel --bg 8080         # https://<기기이름>.<tailnet>.ts.net/app
sudo tailscale funnel --https=443 off   # 끝나면 반드시 끈다
```

Tailscale 기기끼리는 Funnel 없이 Tailscale IP로 직접 붙는다(`tailscale ip -4`로 확인).

> **Funnel 주소와 Tailscale IP는 문서에 적지 않는다.** 이 리포는 공개라, 실제 주소가
> 적혀 있으면 Funnel을 켜는 순간 그 주소를 아는 누구나 접속을 시도할 수 있다. 조회·스트림은
> 무인증이고 PIN은 평문 하드코딩이다([`02`](02_http_api_and_stats.md) §6). 주소는 그때그때
> 기기에서 확인해 쓸 것.

> 🚨 **Funnel은 이 서버를 공개 인터넷에 그대로 연다.** 조회·스트림은 무인증이고 PIN은
> 평문 하드코딩이며 데모 페이지는 사실상 무인증 조작이다([`02`](02_http_api_and_stats.md) §6).
> **켠 채로 두지 말 것.**
>
> 프론트는 API 주소를 `location.origin`으로 쓴다 — 포트를 하드코딩하면 Funnel(외부 포트가
> 8080이 아님)에서 스트림·상태가 안 들어온다. 과거 실제로 밟은 함정이다.

## 9. 경비 모드 운영

```bash
# 촬영물 위치 (컨테이너 밖, 호스트에 그대로 쌓인다)
ls ~/health_care_bot/captures/*.jpg | wc -l
du -sh ~/health_care_bot/captures
tail -3 ~/health_care_bot/captures/guard_log.jsonl
```

- 웹 `/app` → ⚙ → `경비 모드`로 전환하면 홈 정렬 후 5초 뒤 무장된다.
- **자동 정리 로직이 없다.** 파일이 계속 쌓이므로 주기적으로 비워야 한다
  (2026-09-08 기준 207장 / 17 MB, 루트 파티션 73% 사용).
- 사람 사진이므로 `captures/`는 `.gitignore` 대상이다. **밖으로 복사할 때 주의.**

```bash
rm ~/health_care_bot/captures/*.jpg          # 사진만 비우기 (로그는 유지)
```

## 10. 세션 종료 체크리스트

- [ ] `docker stop health-care-bot` (카메라·서보 torque 해제)
- [ ] 서보를 손으로 옮겼거나 재조립했으면 [`06`](06_hardware_calibration.md) §4 절차
- [ ] 작업 내용을 `docs/history/`에 기록 (**커밋 전에 히스토리 먼저** — 프로젝트 관례)
- [ ] 새로 밟은 함정이 있으면 `docs/issues/`에 한 파일로 추가
- [ ] Funnel을 켰으면 `sudo tailscale funnel --https=443 off` (§8)
- [ ] 경비 모드를 썼으면 `captures/` 정리 여부 판단 (§9)
