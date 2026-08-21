# health_care_bot 라인 청사진

본 문서는 본 라인의 목적, 입력/출력, 하드웨어/런타임 결정, 현재 검증 상태, 디렉토리
구조, 문서 지도를 정의합니다. 외부 진입자가 본 라인의 의도와 범위를 30분 안에 파악할
수 있도록 작성합니다.

## 0. 목표

- **입력**: USB UVC 카메라 (640×480, 실측 캡처 ~30 fps)
- **추론**: MoveNet Thunder INT8 TFLite, CPU only (`ai-edge-litert` + XNNPACK, 4 threads)
- **출력**:
  - 17 keypoint (COCO 17점) 좌표 + confidence
  - 관절 각도 — 무릎(hip-knee-ankle) / 어깨 올림(elbow-shoulder-hip)
  - rep 카운트 — **스쿼트 · 숄더프레스 · 사이드 레터럴 레이즈** 3종
  - PTZ 서보 목표각 (yaw/pitch 2축) — 사람을 프레임에 유지
  - HTTP: MJPEG 라이브 스트림 + `stats.json` + 조작 API + 모바일 웹앱
- **사용처**: 헬스케어 코치 로봇 — 운동 횟수 카운팅 + 자세 피드백 + 카메라 자동 추적.
  시연 시 관람객이 QR로 접속해 화면을 보고 카메라를 조작한다.
- **실행 형태**: **단일 도커 컨테이너 / 단일 프로세스** (§2-3)

### 0-1. 실측 현황 (2026-07-26 기준)

| 항목 | 실측 | 참고 기준 (pose 라인 합격선) |
|---|---|---|
| e2e FPS | **11.3~11.4** | ≥ 8 → 충족 |
| 루프 지연 | ~90 ms | — |
| RSS | ~215 MB | ≪ 2.4 GB → 충족 |
| CPU (4코어 합산 100% 기준) | **~83%** | — (여유 17%) |
| SoC 온도 | 51~73°C | ≤ 70°C → **추론 지속 시 초과 관측** |
| dropped_frames | 0 | 0 → 충족 |

FPS 천장 ~11.4는 **invoke(추론) 바운드**다. 근거와 개선 레버는
[`09_performance_roadmap.md`](09_performance_roadmap.md).

## 1. 이 라인의 위치

| 라인 | 폴더 | 관계 |
|---|---|---|
| Vision / ASR / Pose | `unoq-companion-robot/` | 1차 PoC 통과한 3 라인. 라이센스·지연 문제로 vision/asr는 본 라인에서 제외 |
| **health_care_bot (본 라인)** | `health_care_bot/` | **pose 라인 자산(MoveNet Thunder INT8)만 재사용**해 신설한 별도 라인 |

본 라인의 변경은 메인 라인에 영향을 주지 않는다. 모델은
`scripts/copy_model.sh`가 pose 라인에서 복사해 온다(git에 모델 미포함).

## 2. 런타임 / 아키텍처 결정

### 2-1. 채택 — MoveNet Thunder INT8

| 항목 | 값 |
|---|---|
| 파일 | `models/movenet_thunder_int8.tflite` (6.80 MB, 7,126,768 B) |
| 입력 | `[1, 256, 256, 3]` uint8 (letterbox, pad 114) |
| 출력 | `[1, 1, 17, 3]` float32 — 1인 × 17 keypoint × `(y_norm, x_norm, conf)` |
| 런타임 | `ai-edge-litert` + XNNPACK (chipset 비종속) |
| 라이선스 | Apache-2.0 (code) + CC BY 4.0 (model) |

모델 교체(Thunder → Lightning)는 **사용자 지시로 제외**됐다. 정확도를 유지한 채 FPS를
올리는 경로만 검토한다.

### 2-2. 서보는 Linux가 직접 구동한다 (MCU 경유 아님)

UNO Q는 듀얼브레인(A53 Linux + STM32U585 MCU)이지만 **MCU를 런타임에 쓰지 않는다.**
카메라도 서보도 그냥 **USB로 붙인다** — 어차피 카메라 때문에 셀프파워 USB 허브를
UNO Q에 물려 쓰고 있어서, 서보 버스 어댑터도 같은 허브에 꽂아 Linux가 pyserial로
직접 구동한다. MCU 경유가 왜 이 용도로 더 나쁜 선택인지(Router Bridge와 UART가
겹침)는 [`09_performance_roadmap.md`](09_performance_roadmap.md) §6 참고.
`ptz/sketch/health_care_ptz.ino`는 그 시절(MCU 경유 설계) 유물로 런타임 경로에 없다.

### 2-3. 단일 컨테이너 / 단일 프로세스

카메라·추론·서보·웹서버를 쪼개지 않았다. 프로세스 간 통신도 오케스트레이션도 없고,
죽으면 전부 같이 죽는다 — 시연 장비에서 "일부만 살아 있어 원인을 못 찾는" 상태를
만들지 않으려는 선택이다. 웹 프론트엔드에는 런타임이 없다(정적 파일만 읽는다).

상세: [`01_architecture.md`](01_architecture.md)

## 3. 하드웨어 구성 (요약)

```
[셀프파워 USB 허브] ─┬─ [USB 카메라]
                     └─ [Bus Servo Adapter CH343] ─ [yaw ST3215 ID=1] ─ [pitch ID=2]
        │
   [UNO Q: QRB2210, Cortex-A53 x4, 4GB RAM]
```

| 항목 | 값 |
|---|---|
| 중앙 기준 | tick 2047 = **180°** (EEPROM Homing_Offset 캘리브레이션 완료) |
| 실측 가동범위 | yaw 90~270° (±90) / pitch 150~210° (±30) |
| 회전 속도 | 569 tick/s ≈ 50 deg/s (옛 PWM 20ms/° 등가) — 안전상 고정 |
| 서보 버스 | `/dev/ttyACM0` (PC는 `COM9`), 1,000,000 baud |

> **셀프파워 허브가 필수다.** UNO Q는 USB 호스트 VBUS를 공급하지 않아
> (`usb_vbus=disabled`) 버스파워 장치는 enumeration 자체가 안 된다.

상세·캘리브레이션 절차: [`06_hardware_calibration.md`](06_hardware_calibration.md)

## 4. 현재 검증 상태

### 4-1. 실기에서 검증된 것

- 통합 파이프라인 — 웹서버 + 카메라 + MoveNet + 카운터 3종 + PTZ가 `main.py` 하나로
  동시 구동, 크래시 없음
- **PTZ yaw 추적** — 무릎/어깨 중점 추적, 중앙 4/6 섹터 밴드, 획득→잠금으로 "도리도리" 제거
- **손실 복구(관성)** — 프레임 밖으로 나가도 이탈 속도로 관성 추적, 못 찾으면
  대기→복귀→중앙 순으로 물러남. 재검출 시 즉시 정상 복귀
- 시간(deg/s) 기준 제어 — PC(29 FPS)와 UNO Q(11 FPS)에서 같은 각속도
- 시작 시 서보 자동 중앙 정렬 / 서보 없을 때 graceful degrade
- 웹 `:8080/app` 단일화 + 종목 3버튼 + 실기 카메라 연동 + 모바일 접속
- `--idle-skip-draw` 게이팅 (뷰어 0명 시 인코딩 skip, 이득 ~0.1~0.3 fps)

### 4-2. 아직 신뢰할 수 없는 것 / 미측정

| 항목 | 상태 |
|---|---|
| **스쿼트 rep 신뢰성** | 실기에서 `bottom=5°`(해부학적 불가능) 가짜 rep 관측. 원인은 2D 투영 왜곡 + rep 하나가 유효 샘플 2개로 성립하는 구조. **대응 보류 중** ([`04`](04_algorithm_exercise.md) §6) |
| 3종 임계 실측 튜닝 | 현재 값은 합리적 기본값일 뿐 — 실제 사람으로 검증 필요 |
| 상체 프레이밍 | 숄더프레스/레터럴에서 머리 위 팔이 프레임에 남는지 실측 안 됨 |
| 검출 안정성 | `ptz=lost`가 90프레임(~8초) 연속 나온 구간 있었음 — 거리/화각/조명 미규명 |
| 다중 동시 접속 | `/stream.mjpg`가 커넥션당 스레드 1개 점유. 부하 미검증 |
| NPU 델리게이트 | 조사 미착수 (FPS 올릴 유일한 큰 레버) |

우선순위: [`09_performance_roadmap.md`](09_performance_roadmap.md) §2

## 5. 디렉토리 구조

```
health_care_bot/
├── README.md              진입점 (요약 + 빠른 실행)
├── src/                   런타임 — 컨테이너가 실행하는 전부
│   ├── main.py            통합 진입점: 루프 + CLI + 텔레메트리
│   ├── pose_utils.py      keypoint 상수 / letterbox / 중심점 헬퍼 / draw
│   ├── angles.py          knee_angle, shoulder_elev_angle, pick_angle
│   ├── exercise_counter.py  RepCounter + Squat/OverheadPress/LateralRaise
│   ├── ptz_controller.py  PTZ 추적 + 손실 복구 + 서보 직결
│   ├── st3215_bus.py      ST3215 프로토콜 저수준 드라이버
│   ├── http_server.py     MJPEG + stats.json + /api/* + /app 서빙
│   └── app_state.py       세션 상태 + 운영자 PIN 제어권 lock
├── web/dist/index.html    ★ 현재 /app으로 서빙되는 애플 "Fluid" 정적 페이지
├── web/src/               Vite+React 시안 6종 (현재 서빙 안 됨)
├── design_demos/          독립 HTML 시안 2종 (Fluid 원본 / Field Optics)
├── docker/                Dockerfile · requirements.txt · run.sh
├── models/                movenet_thunder_int8.tflite (git 미포함)
├── scripts/               벤치·도구 (런타임 아님)
├── ptz/sketch/            MCU 스케치 — 현재 미사용
├── stl/                   짐벌 하우징 3D 모델
├── docs/                  §6
└── backup/                복원점 3개
```

## 6. 문서 지도

### 6-1. 상설 문서 (docs/00~09) — "지금 어떻게 동작하는가"

| # | 문서 | 담는 것 |
|---|---|---|
| 00 | **본 문서** | 청사진 · 실측 현황 · 검증 상태 · 문서 지도 |
| 01 | [`01_architecture.md`](01_architecture.md) | 프로세스/스레드, 모듈 경계, 상태 소유권, degrade 경로 |
| 02 | [`02_http_api_and_stats.md`](02_http_api_and_stats.md) | HTTP API 계약 + `stats.json` 전체 스키마 |
| 03 | [`03_algorithm_ptz_tracking.md`](03_algorithm_ptz_tracking.md) | PTZ 제어 법칙 + 관성 손실 복구 + 튜닝 |
| 04 | [`04_algorithm_exercise.md`](04_algorithm_exercise.md) | 종목별 각도·카운팅 상태기계 + 실패 모드 |
| 05 | [`05_web_ui_fluid.md`](05_web_ui_fluid.md) | 웹 UI (Fluid) — 화면·조작·배포 |
| 06 | [`06_hardware_calibration.md`](06_hardware_calibration.md) | 하드웨어 값 + 캘리브레이션/재조립 절차 |
| 07 | [`07_runbook.md`](07_runbook.md) | 실행·배포 런북 (디바이스/PC, 환경 확인) |
| 08 | [`08_troubleshooting.md`](08_troubleshooting.md) | 함정 색인 — 증상에서 원인으로 |
| 09 | [`09_performance_roadmap.md`](09_performance_roadmap.md) | 성능 실측 + 다음 할 일 우선순위 |

### 6-2. 기록 (append-only) — "언제 무엇이 있었나"

| 폴더 | 규칙 |
|---|---|
| [`history/`](history/) | 의사결정·작업 경위. **한 사건 한 파일**, `YYYY-MM-DD_NN_주제.md` |
| [`issues/`](issues/) | 문제와 재발 방지. 증상 → 원인 → 해결 → 재발 방지 |

세션 인수인계는 history의 `*_session_handoff.md`가 담당한다. 가장 최신:
[`history/2026-08-08_01_session_handoff.md`](history/2026-08-08_01_session_handoff.md).

### 6-3. 웹 프론트 부속 문서

| 문서 | 상태 |
|---|---|
| [`../web/ARCHITECTURE.md`](../web/ARCHITECTURE.md) | 웹 설계 근거(왜 PWA·왜 폴링·왜 PIN). 유효 |
| [`../web/DESIGN.md`](../web/DESIGN.md) | 시안·서체·색 근거. **07-21 기준으로 오래됨**(CALM 1종으로 서술, 실제 6종) |
| [`../APP_GUIDE.md`](../APP_GUIDE.md) | React 시절 실행 가이드. `--mode auto`·푸시업 등 **낡은 서술 있음** |

## 7. 문서 규칙

- **상설 문서(00~09)는 갱신한다.** 현재 동작과 어긋나면 고치는 것이 원칙이다.
- **history/issues는 고치지 않는다.** 그 시점의 기록이므로 나중에 틀렸다고 판명되면
  새 파일로 정정하고, 옛 파일은 그대로 둔다(파일 경로 변경에 따른 링크 수정은 예외).
- **작업 즉시 기록한다** — 커밋 전에 history를 먼저 쓴다(프로젝트 관례).
- **수치는 코드에서 확인해 적는다.** 문서를 문서로부터 베끼지 않는다.
- 멘토 패키지(`docs/mentor/`)는 대외비이며 `.gitignore` 대상이다. 본 문서군에서
  출처·파일명·티켓 번호를 노출하지 않는다.
   