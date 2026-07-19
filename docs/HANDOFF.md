# health_care_bot 핸드오프 (2026-07-17 기준)

다음 세션 시작 시 이 문서부터 읽으면 맥락이 잡힙니다.
상세 경위는 `docs/history/`, 재발방지는 `docs/issues/` 참고.

---

## 1. 한 줄 요약

UNO Q용 헬스케어 코치 로봇. **카메라 → MoveNet 포즈 → 스쿼트/푸시업 카운팅 +
PTZ 카메라 추적 → 웹앱(PWA)** 이 한 프로세스(`src/main.py`)에서 돈다.
현재는 **개발 PC에서 서보 직결로 통합 동작까지 확인된 상태**이고, UNO Q 실기
배포는 아직이다.

---

## 2. 실행 방법 (환경 함정 포함 — 중요)

```powershell
cd C:\Project\health_care_bot

# 통합 실행 (웹앱 + 카운팅 + PTZ)
py -3.14 src/main.py models/movenet_thunder_int8.tflite --camera 0 --serial COM9 --serve 8080
# 브라우저: http://localhost:8080/app          (뷰어)
#           http://localhost:8080/app?role=operator  (운영자, PTZ 수동조작)

# PTZ 추적만 단독 테스트 (OpenCV 창, q=종료 r=카운트리셋)
py -3.14 scripts/ptz_camera_track.py --port COM9 --camera 0 --drive
```

**함정 4가지 (매번 걸림)**

1. **반드시 `py -3.14`** — 이 PC엔 파이썬이 둘이고 아나콘다 `base`엔 `cv2`가
   없다. 필요한 패키지(cv2/numpy/pyserial/ai-edge-litert)는 Python 3.14에만 있음.
2. **카메라 인덱스가 USB 재연결마다 뒤바뀐다.** 현재 **짐벌=0, 내장웹캠=1**
   (이전엔 반대였음). 헷갈리면 각 인덱스에서 한 장 캡처해 눈으로 확인할 것.
3. **서보 전원(6~12.6V)은 USB와 별개.** 전원이 없으면 포트는 정상으로 열리는데
   ID 1~5 전부 무응답이 된다 → COM 포트/ID 문제로 오해하기 쉬움. 어댑터 배럴잭
   먼저 확인.
4. 서보 포트는 **COM9 (USB-Enhanced-SERIAL CH343)**, baud 1,000,000.

### 디바이스(UNO Q) 접속

| 항목 | 값 |
|---|---|
| 호스트 | `unoq-korea01` / 사용자 `arduino` |
| IP | `192.168.0.45` (DHCP — 바뀌면 `adb shell "hostname -I"`로 재확인) |
| 앱 루트 | `/home/arduino/health_care_bot` |
| venv | `~/venv-unoq` (컨테이너 밖에서 파이썬 쓸 때) |
| adb serial | `1204329696` |

**SSH가 기본 (권장).** 2026-07-19에 키 등록 완료 — 비번 없이 붙는다.

```powershell
ssh arduino@192.168.0.45
```

> **SSH는 네트워크로 붙으므로 PC-USB 연결이 필요 없다.** adb를 쓰려고 USB-C를
> 물고 있으면 그 포트에 허브+카메라를 못 꽂는데, SSH로 작업하면 USB-C를 비워
> 카메라를 연결할 수 있다. 단 UNO Q가 그 포트로 **전원**을 받고 있지 않은지
> 먼저 확인할 것.

**adb (USB 연결 시):**

```powershell
$ADB = "$env:LOCALAPPDATA\Arduino15\packages\arduino\tools\adb\32.0.0\adb.exe"
& $ADB devices
```

**코드 배포** — 함정 2건(§6) 때문에 순서가 정해져 있다:

```powershell
$APP = "/home/arduino/health_care_bot"
& $ADB shell "rm -rf $APP/src"      # 먼저 지운다 (안 지우면 src/src/로 중첩)
& $ADB push src "$APP/src"
& $ADB shell "cd $APP; md5sum src/*.py"   # push 로그 믿지 말고 해시 대조
```

**디바이스에서 실행:**

```bash
cd /home/arduino/health_care_bot
v4l2-ctl --list-devices          # 진짜 카메라 노드 확인 (Venus가 0,1 선점)
CAMERA_DEV=/dev/video2 bash docker/run.sh
```

---

## 3. 하드웨어 현재 상태

| 항목 | 값 |
|---|---|
| yaw 서보 | ID=1 (체인 첫 번째) |
| pitch 서보 | ID=2 (yaw에서 데이지체인) |
| 중앙 기준 | tick 2047 = **180°** (EEPROM Homing_Offset 캘리브레이션 완료) |
| yaw 실측 가동범위 | 90~270° (중앙 ±90°) |
| pitch 실측 가동범위 | 150~210° (중앙 ±30°) |
| 회전 속도 | 569 tick/s (20ms/° 등가, 손가락 끼임 방지) |
| pitch 방향 | 180에서 **줄어들면 카메라가 위**, 늘어나면 아래 (2026-07-19 실측). `pitch_sign=+1`이 정상 |

**재조립/캘리브레이션이 틀어졌을 때** — 짐벌을 원하는 정면 자세로 손으로 맞춰둔 뒤:

```powershell
py -3.14 scripts/calibrate_st3215.py --port COM9 calibrate   # 지금 자세를 중앙으로 재정의(서보 안 움직임)
py -3.14 scripts/calibrate_st3215.py --port COM9 stop        # 긴급정지(torque OFF)
```

---

## 4. 지금까지 검증된 것

- **통합 파이프라인 동작**: 웹서버(:8080, `/app` 뷰어·운영자) + 카메라 + MoveNet
  + 카운터 + PTZ가 `main.py` 하나로 동시 구동. 크래시 없음.
- **시작 시 서보 자동 중앙 정렬** (이전 실행에서 틀어져 있어도 매번 180/180에서 시작).
- **yaw 추적** 실기 확인 — 무릎 중점 추적, 중앙 4/6 섹터 밴드, 획득→잠금으로
  "도리도리" 제거됨. **yaw 부호는 기본값(+1)이 맞음.**
- **한쪽 다리 쏠림 해결** — 양쪽 무릎이 다 보일 때만 무릎 중점을 쓰고, 한쪽만
  보이면 엉덩이 중심으로 폴백.
- **시간(초) 기준 제어** — 추적 속도가 deg/s로 표현돼 **프레임레이트와 무관**하다.
  PC(29 FPS)와 UNO Q(11 FPS)에서 같은 각속도가 나온다. 이전에는 프레임당 고정
  이동이라 11 FPS에서 각속도가 64% 부족해 "톡톡" 끊겼다.
- **카메라를 벗어나도 관성을 통한 추적** — 사람이 빠르게 프레임 밖으로 나가면
  마지막 yaw 각속도로 관성 추적을 이어간다(10프레임, 감쇠). 못 찾으면
  1초 대기 → 관성 이전 위치 복귀 → 2초 대기 → 중앙 복귀 순으로 물러나고,
  **어느 단계든 재검출되면 즉시 정상 추적으로 복귀**한다. 정지 중 손실(각속도 0)
  이면 관성이 걸리지 않아 헛발질하지 않는다. 로그 태그 `COAST`/`BACK`/`CENTER`.
- **서보 없을 때 graceful degrade** — disabled 모드로 떨어지고 웹 UI는 정상 동작.

**스쿼트 카운팅은 아직 신뢰할 수 없다** — 합성 시퀀스로는 정상이지만, 실기
첫 측정에서 `bottom=5°`(해부학적으로 불가능)인 가짜 rep이 잡혔다. 2D 투영
왜곡 + rep 하나가 유효 샘플 2개로 성립하는 구조가 원인. 상세와 대응 보류
근거는 [`history/2026-07-19_02`](history/2026-07-19_02_ptz_time_based_control_and_loss_recovery.md).

---

## 5. 다음 할 일 (우선순위)

### 5-1. 실제 스쿼트로 카운팅 + 추적 동시 실측
**무릎 각도는 hip·knee·ankle 3점이 모두 보여야 계산된다** → 발목까지 프레임에
들어오는 거리에서 테스트해야 카운팅이 동작한다.

### 5-2. UNO Q 실기 배포
`docker/run.sh`의 `SERIAL_DEV`는 이제 `/dev/ttyUSB0`(서보 버스 어댑터) 기본값.
실기에서 `ls /dev/ttyUSB*`로 실제 노드 확인 후 지정. 카메라는 Venus 코덱이
`/dev/video0·1`을 선점하므로 보통 `/dev/video2` 이상.

### 5-3. (보류 중) MCU 듀얼브레인 트랙
UNO Q는 듀얼브레인인데 현재 MCU를 런타임에 전혀 안 쓴다. 리서치 결론:
Linux↔MCU는 **Router Bridge(Unix 소켓 msgpack RPC)로만** 가능하고 raw serial
경로는 없다. 서보를 MCU에 배선할 방법이 없어(사용자 확인) **사용자 지시로 잠정
보류**. 계획 문서만 남아있음.

---

## 6. 알려진 함정 (재발 방지)

| 함정 | 요약 |
|---|---|
| **Homing_Offset 부호비트** | STS3215은 `Homing_Offset`=bit11, `Present_Position`=bit15로 **다르다**. 혼동해서 음수 오프셋을 잘못 인코딩 → 서보 폭주 → **3D 출력물 파손 이력**. `docs/issues/2026-07-17_01_...` |
| **torque ON 상태 EEPROM 변경 금지** | offset을 torque 켠 채 바꾸면 옛 Goal_Position으로 실제 회전. 반드시 torque off → 계산 → goal 동기화 → on 순서 (`calibrate` 명령이 자동 처리) |
| **서보 ID 변경은 즉시 반영** | "전원 재투입 필요"라는 일반 SDK 문구와 다름. `set-id` 실패 로그가 떠도 새 ID로 ping해 확인할 것 |
| **cp949 콘솔 유니코드 크래시** | `—`(em-dash), `⚠` 등이 Windows 콘솔에서 `UnicodeEncodeError`. 코드/주석에 쓰지 말 것 |
| **adb는 PowerShell로** | Git Bash는 경로를 멋대로 변환해 push가 조용히 실패 |
| **디렉토리 push 전 remote `rm -rf`** | remote 경로가 이미 있으면 `adb push`가 그 안에 `src/src/`로 중첩시킨다. 구버전이 그대로 서빙돼 "반영 안 됨"으로 보임 |
| **디바이스 SSH 세션 안에서 PC용 명령 실행** | SSH로 들어간 뒤 PowerShell 명령(`$var = ...`)을 붙여넣으면 bash `syntax error`. 더 나쁜 건 `ssh arduino@...`를 또 실행해 **자기 자신에게 재접속**하는 것. 프롬프트가 `arduino@unoq-korea01:~$`인지 먼저 볼 것 |
| **PowerShell 파이프로 `authorized_keys` 등록 금지** | PS 5.1은 파이프 출력에 CRLF/BOM을 섞어 키가 조용히 깨진다. 디바이스 셸에서 `echo '<pubkey>' >> ~/.ssh/authorized_keys`로 직접 넣을 것 |
| **PD허브 카메라 미인식** | 허브를 PC에 한 번 꽂았다 빼면 초기화되어 정상 인식 |
| **`cv2.CAP_PROP_BUFFERSIZE` 신뢰 금지** | 드라이버가 무시함. `FrameGrabber`(최신 프레임만 유지)로 해결됨 |

---

## 7. 파일 지도

```
src/                      런타임 (도커 컨테이너가 실행)
├── main.py               통합 진입점 — 루프 + CLI
├── ptz_controller.py     PTZ 추적 + 서보 버스 직결 (v2 로직 이식됨)
├── st3215_bus.py         ST3215 프로토콜 저수준 드라이버
├── pose_utils.py         keypoint 상수 + letterbox + 중심점 헬퍼(무릎/엉덩이/몸통)
├── angles.py             knee/elbow 각도, 자세 분류
├── exercise_counter.py   SquatCounter / PushupCounter (히스테리시스+dwell)
├── http_server.py        PWA 서빙 + MJPEG + REST API (PTZ 통합 시 무변경)
└── app_state.py          세션 + 운영자 PIN 락

scripts/                  벤치/도구 (런타임 아님)
├── ptz_camera_track.py       PTZ+스쿼트 단독 테스트 (작업본)
├── ptz_camera_track_v1.py    백업: PTZ 추적만
├── ptz_camera_track_v2_ptz_squat.py  백업: PTZ+스쿼트
├── calibrate_st3215.py       중앙 재캘리브레이션 / 긴급정지
└── test_st3215_serial.py     ping/read/move/sweep/set-id/dual-spin

web/                      Vite+React PWA (빌드 산출물 web/dist)
ptz/sketch/               MCU 스케치 (현재 미사용 — MCU 트랙 보류)
backup/pre_web_integration/   통합 직전 복원점 (src, scripts, docker 전체)
```

**되돌리기**: 통합을 물리려면 `backup/pre_web_integration/`의 `src`, `scripts`,
`docker`를 프로젝트 루트에 덮어쓰면 된다.

---

## 8. 핵심 설정값 (튜닝 지점)

`src/ptz_controller.py` 상단 dataclass 필드 — 전부 `main.py` CLI 플래그로도 조절 가능.

| 값 | 기본 | 의미 |
|---|---|---|
| `sector_side` | 1/6 | 좌우 1/6·중앙 4/6·1/6. 무릎을 중앙 4/6 밴드에 유지 |
| `pitch_target_y` | 0.62 | 무릎을 화면 세로 어디에 둘지 (0=위, 1=아래) |
| `pitch_deadzone` | 0.20 | 상하 허용 오차. 넓게 잡아 **스쿼트 상하 동작을 무시** |
| `lock_frames` | 10 | 존 안에 N프레임 머물면 잠금(정지) |
| `reengage` | 0.18 | 잠금 해제 임계 (히스테리시스) |
| `track_scale` | 0.5 | 추적 속도 1/2 |
| `both_knee_scale` | 0.5 | 양 무릎 보이면 추가 1/2 (총 1/4) |

> pitch가 0.5/0.10이던 시절엔 (1) 무릎이 원래 화면 아래(0.79)라 잠금이 영영 안
> 걸리고 (2) 스쿼트마다 카메라가 끄덕였다. 0.62/0.20으로 바꿔 둘 다 해결.
> 좌우(yaw)는 이 값들과 무관 — 섹터 밴드로 따로 판정한다.
