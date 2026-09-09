# 웹 UI — Fluid (`:8080/app`)

본 문서는 현재 로봇이 서빙하는 **유일한 화면**인 애플 디자인 페이지 "Fluid"를 정리합니다.
화면 구성, 서버와 주고받는 값, 조작 경로, 배포 방법, 함정을 담습니다.

- 서버 쪽 API 계약·스키마: [`02_http_api_and_stats.md`](02_http_api_and_stats.md)
- 상위 설계 근거(왜 PWA·왜 폴링·왜 PIN): [`../web/ARCHITECTURE.md`](../web/ARCHITECTURE.md)

## 0. 가장 먼저 알아야 할 것

**Fluid가 이 로봇의 확정 UI다** (2026-09-08 확정). 후보가 아니라 고정이고, 웹 작업은
전부 이 파일에서 한다. `web/src/`의 React 계층은 **보관 상태**이며 되살릴 계획이 없다.

**`/app`은 React 앱이 아니다.** 자체 포함(self-contained) 정적 HTML **파일 하나**다.
CSS·JS·QR SVG가 전부 그 안에 인라인되어 있고, 빌드 단계도 의존성도 없다.

```
web/app/index.html   ← 이 파일 하나가 /app 이다  (약 48 KB, <title>Health Care Bot — Fluid</title>)
```

`web/src/`의 Vite+React 코드베이스는 **서빙되지 않는 보관 계층**이고, 그 빌드 산출물은
`web/dist/`(gitignore)에 떨어진다. 서버는 `web/app` → `web/dist` 순으로 찾으므로
**`npm run build`를 돌려도 `/app`은 Fluid 그대로다**(§9-1).

| 경로 | 정체 |
|---|---|
| `web/app/index.html` | **현재 `/app`** — Fluid (배포본, 유일한 최신본, **커밋됨**) |
| `design_demos/live_apple-design.html` | Fluid 초기 원본 — **2026-07-26에서 멈춰 있다(§9)** |
| `web/dist/` | React 시안 빌드 산출물 — gitignore. `/app/assets/*`로만 노출 |
| `design_demos/live_frontend-design.html` | 다른 시안 "Field Optics" (서빙 안 함) |

> ⚠️ **`design_demos/live_apple-design.html`는 더 이상 작업본이 아니다.** 경비 모드 UI·QR
> 생성기·`location.origin` 수정이 전부 빠진 옛 버전이다. 되돌리기용으로 쓰면 안 된다(§9).

접속: `http://192.168.0.50:8080/app` — 뷰어·운영자 구분 없이 **접속하면 바로 조작 가능**
(§4).

## 1. 화면 구성

```
┌───────────────────────────────────────────┐
│ ● Health Care Bot  [Live · Robot] [⊞][⚙] │  상단바: 상태 pill + 모바일QR + 설정
├───────────────────────────────────────────┤
│                                           │
│         [로봇 카메라 /stream.mjpg]         │  뷰포트
│              + 레티클(추적점)              │  · 스켈레톤은 서버가 이미 구움
│              "ROBOT CAM · 실시간"          │  · 레티클 = person_center_norm
│                                           │
│    ◯ 7/20   스쿼트                        │  진행 링 + 횟수 + 종목명
│             "좋은 깊이입니다. 올라오세요"   │  자세 피드백 한 줄
├───────────────────────────────────────────┤
│  [ 스쿼트 | 숄더프레스 | 레터럴 ]          │  종목 세그먼트 → POST /api/mode
│    (⚙ 안에 [운동 모드 | 경비 모드] 전환)    │  경비 모드는 설정 시트에서 분리
├───────────────────────────────────────────┤
│  카메라 · PTZ                    [EDGE]    │
│  [ 자동 추적 | 직접 조작 ]                 │
│    자동 → FPS / 추론ms / CPU°C / RAM       │  텔레메트리 칩 4개 + CPU 막대
│    수동 → 조이스틱 + PAN/TILT 수치         │
└───────────────────────────────────────────┘
```

**자동/수동 토글이 같은 자리를 공유한다** — 자동 추적일 때는 조종할 게 없으니 그 공간에
텔레메트리를 보여주고, 직접 조작으로 바꾸면 조이스틱이 나타난다.

**⊞ → 모바일 접속 시트**: QR과 URL(`location.origin + pathname`)을 띄운다. 복사 버튼 포함.
**QR은 페이지 안에서 그 자리에 인코딩한다**(`qrSvg()`, 버전1~4·ECC-M·마스크0 고정, 외부
CDN 없음). 예전엔 특정 IP로 미리 렌더링해둔 정적 SVG라 IP가 바뀌어도 안 바뀌는 함정이었다.

**⚙ → 설정 시트**: `[운동 모드 | 경비 모드]` 전환 세그먼트. 경비 모드에서는 진행 링이
무장 잔여 초 → 촬영 매수로 바뀌고, "🖼 사진 보기"(촬영 갤러리 시트 + 라이트박스)와
"● 직접 촬영"(`POST /api/guard/capture-now`) 버튼이 PTZ 패널 좌측에 붙는다.

## 2. 라이브 판정과 데모 폴백

500 ms마다 `/stats.json`을 폴링한다(`setTimeout` 체인).

```
성공 1회 → enterLive()
   pdot 녹색 · "Live · Robot" · 뷰포트를 /stream.mjpg 로 교체 · 제어권 확보 시도

연속 실패 3회 & 아직 한 번도 성공 못 함 → startDemo()
   pdot 황색 · "Demo" · getUserMedia(전면 카메라) · 합성 수치 순환
```

데모는 **로봇 없이 노트북에서 화면을 보여줄 때**를 위한 것이다. 합성 텔레메트리는 실측
범위에 맞췄다(FPS 10.8, 추론 92 ms, CPU 58°C / 83%, RAM 412 MB). 카메라 권한이 거부되면
"카메라 권한 필요 · 눌러서 다시 시도" 버튼이 남는다.

> **라이브가 한 번 잡히면 데모로 되돌아가지 않는다**(`if(demoStarted||LIVE)return`).
> 실기 동작 중에 데모 화면이 끼어드는 사고가 구조적으로 불가능하다.

## 3. 서버에서 읽는 값

`stats.json` → 화면 매핑. 전부 방어적으로 접근한다(`d.ptz||{}` 형태).

| 화면 요소 | 출처 |
|---|---|
| 레티클 위치 | `person_center_norm` → `(x-0.5)*W`, `(y-0.42)*H`, 스프링으로 이동 |
| 종목 세그먼트 · 종목명 | `app.session.mode` (overhead/lateral만 인정, 그 외 squat) |
| 횟수 / 목표 | `d[mode].reps` / `app.session.target_reps` (기본 20) |
| 진행 링 | `reps / target` |
| PTZ 상태 배지 | `ptz.auto_track_enabled ? ptz.state.toUpperCase() : "MANUAL"` |
| PAN / TILT 수치 | `ptz.pan_deg - 180`, `ptz.tilt_deg - 180` (**중앙 기준 상대각**) |
| 텔레메트리 칩 | `fps`, `loop_ms`, `cpu_temp_c`, `rss_mb` |
| CPU 막대 | `cpu_percent` (0~100 클램프, `null`이면 `—%`) |
| 자세 피드백 | `ptz.state` + `app.session.status` + `exercise_active` + `angle_deg.used` |

**서버 값이 `null`일 수 있다는 걸 전제로 만들었다** — `cpu_percent`의 첫 응답은 항상
`null`이고, PC에서 돌리면 온도·RAM도 `null`이다. 전부 `—`로 표시된다.

### 3-1. 자세 피드백 우선순위

```
1. ptz.state == "lost"     → "사람을 찾는 중입니다…"
2. ptz.state == "edge"     → "프레임 가장자리 — 따라갑니다."
3. session.status == idle  → "준비되면 시작하세요. 로봇이 지켜봅니다."
4. 종목별:
   squat    DOWN이고 각도<100 → "좋은 깊이입니다. 올라오세요."
            DOWN이고 각도≥100 → "조금 더 깊이 앉아보세요."
            UP                → "무릎·발끝 정렬 안정적입니다."
   overhead UP → "팔을 끝까지 펴세요" / 아니면 "팔을 머리 위로 곧게 올리세요"
   lateral  UP → "어깨 높이까지 수평으로" / 아니면 "팔을 옆으로 어깨 높이까지"
```

**추적 상태가 운동 상태보다 우선한다.** 사람을 놓친 상황에서 자세 조언을 하는 건
무의미하기 때문이다.

## 4. 제어권 — 지금은 "누구나 조종" 상태

```javascript
clientId = "hcb-demo"                       // 모든 클라이언트가 동일
post("/api/control/claim", {pin: opPin})    // 자동 claim (opPin 기본 "1234")
setInterval(() => post("/api/control/heartbeat"), 30000)   // 30초마다 연장
```

서버의 제어권 lock은 원래 "운영자 1명"을 전제로 만들어졌지만(60초 lock, PIN), 이 페이지는
**모든 접속자가 같은 `client_id`를 공유**하도록 만들어져 있다. 그 결과:

- PIN 입력 화면이 없다 — 접속하면 바로 조작된다. 단 서버가 `HCB_OPERATOR_PIN`으로
  PIN을 바꿔 놓았으면 `invalid_pin`이 돌아오고, **그때만** `prompt()`로 한 번 묻고
  `localStorage`(`hcb.operator_pin`)에 기억한다. 기본값을 쓰는 평소에는 안 묻는다.
- 여러 사람이 동시에 조작할 수 있고 **마지막 명령이 이긴다**(격리 없음).
- 시연 편의를 위한 의도적 선택이다. 조작을 한 사람에게 묶어야 한다면 `clientId`를 기기별
  랜덤값으로 바꾸고 PIN 입력 UI를 붙여야 한다.

> **보안상 의미**: `/stats.json`·`/stream.mjpg`는 애초에 무인증이고, 여기에 더해 PTZ·세션
> 조작까지 사실상 무인증이다. **로컬 LAN 전용**이라는 전제가 깨지면 안 된다.
> Tailscale Funnel(`README.md` §3.2)을 켜는 순간 이 전제가 깨진 채 공개 인터넷에 열린다 —
> 보여줄 때만 켜고 반드시 끌 것.

## 5. 조작 경로

| 조작 | 요청 | 비고 |
|---|---|---|
| 종목 선택 | `POST /api/mode {mode}` | squat / overhead / lateral |
| 자동↔수동 토글 | `POST /api/ptz {command:"auto_track", enabled}` | 서버의 `auto_track_enabled` 반영 |
| 방향 버튼 | `POST /api/ptz {command:"pan"\|"tilt", delta_deg: ±6}` | |
| 조이스틱 드래그 | 같은 API, `delta_deg = ±8` 범위로 연속 전송 | 220 ms 주기, 데드존 있음 |

**낙관적 UI + 되감기 방어** — 버튼을 누르면 서버 응답을 기다리지 않고 즉시 세그먼트가
움직이고(`pendingMode`), **1.5초(PTZ는 2초) 동안은 서버 값이 UI를 덮어쓰지 못한다.** 폴링이
500 ms 간격이라, 이 창이 없으면 서버가 아직 갱신되지 않은 옛 값을 돌려줘 방금 누른 버튼이
되감기는 현상이 생긴다.

조이스틱은 라이브에서 **실제 서보를 돌린다.** 데모 모드에서는 서보 대신 로컬 카메라 영상이
조이스틱 방향으로 살짝 밀리는 시각 피드백만 준다.

## 6. 모션 · 접근성

apple-design 원칙을 구현하려고 **스프링 엔진을 직접 넣었다**(라이브러리 없음).

```javascript
class Spring { ... }  .config(damping, response)
ringSpring  0.5 / 0.15     진행 링
numSpring   0.35 / 0.4     횟수 숫자 (1.18 → 1 팝)
knob        0.35 / 0.28    세그먼트 노브
retX/retY   0.5 / 0.12     레티클 추적
aim         기본값          조이스틱 (러버밴딩 rubber(o,dim,c))
```

- 횟수가 오를 때 숫자가 팝 + `navigator.vibrate(9)` 햅틱.
- 조이스틱은 한계 밖으로 끌면 **러버밴딩**으로 저항한다.
- `prefers-reduced-motion` → 트랜지션 제거 + **햅틱도 끈다.**
- `prefers-reduced-transparency` → `backdrop-filter` 제거 + 불투명 배경으로 교체.

## 7. 레이아웃 — 기기별로 다른 화면

| 폭 | 형태 |
|---|---|
| **< 820 px (폰)** | `100dvh` **한 화면**. 카메라가 `flex`로 줄어들어 컨트롤이 항상 스크롤 없이 들어온다. `env(safe-area-inset-bottom)` 반영 |
| **≥ 820 px (컴퓨터)** | 여유 있는 배치. **카메라를 줄이지 않고 크게** 두고 정보 패널을 함께 배치, 페이지가 스크롤됨 |

폰에서 스크롤이 생기면 시연 중 "화면이 잘렸다"가 되기 때문에, 폰 쪽만 한 화면에 고정하는
방향으로 분기했다.

## 8. 견고성

`onLive()` 전체가 `try/catch`로 감싸여 있고, 모든 필드 접근이 방어적이다.

```javascript
catch(err){ /* one bad frame must never freeze the live loop */ }
```

**한 프레임의 stats가 이상해도 라이브 루프가 멈추지 않는다.** 폴링은 다음 tick을 항상 걸기
때문에 예외가 나도 계속 돈다. 시연 중 화면 프리징이 가장 치명적이라 이렇게 잡았다.

## 9. 수정과 배포

**배포본이자 유일한 최신본은 `web/app/index.html` 하나다. 여기를 직접 고친다.**

> 2026-09-09 이전에는 `web/dist/index.html`이었다. `dist`가 gitignore 대상이라
> **클론하면 `/app`이 503**이 되는 문제가 있어 커밋되는 `web/app/`으로 옮겼다.
> 서버는 `web/app` → `web/dist` 순으로 찾으므로 아직 옮기지 않은 디바이스도 그대로 뜬다.

`design_demos/live_apple-design.html`은 한때 작업본이었지만 **2026-07-26 이후 갱신이
끊겼다.** 두 파일은 더 이상 같지 않다:

| 파일 | 크기 | 최종 | 경비 모드 UI |
|---|---|---|---|
| `web/app/index.html` | 49,022 B | 2026-08-08 | **있음** |
| `design_demos/live_apple-design.html` | 32,358 B | 2026-07-26 | **없음** |

JS가 전부 인라인이라 빌드가 없는 대신 **문법 오류를 잡아줄 단계도 없다.** 배포 전에
`<script>` 블록만 임시 파일로 떼어 `node --check`로 확인하거나(과거 세션의 검증 방식),
최소한 브라우저 콘솔을 한 번 열어볼 것.

```bash
# 배포본은 자체포함 단일 파일(48 KB)이라 이것 하나만 올리면 된다
scp web/app/index.html arduino@192.168.0.50:~/health_care_bot/web/app/index.html
```

디바이스를 git으로 관리한다면 `git pull`만으로도 반영된다 — 배포본이 커밋되기 때문이다.

`http_server`가 **매 요청마다 디스크에서 읽으므로 컨테이너 재시작이 필요 없다.** 브라우저
새로고침만으로 반영된다(`.html`은 `Cache-Control: no-store`).

### 9-1. `npm run build`는 더 이상 이 페이지를 덮지 않는다

예전에는 배포본이 Vite 빌드의 산출물 경로(`web/dist/index.html`)에 있어서, React 쪽을
빌드하면 **Fluid가 stock React 앱으로 교체됐다.** 배포본을 `web/app/`으로 분리하고 서버가
`web/app`을 먼저 보게 하면서 이 함정은 사라졌다 — 빌드해도 `/app`은 Fluid 그대로다.

> 🚨 **`cp design_demos/live_apple-design.html web/app/index.html`을 실행하지 말 것.**
> 경비 모드 UI·QR 생성기·`location.origin` 수정이 통째로 롤백된다. Fluid를 되돌려야 하면
> `backup/2026-08-08_guard_mode_qr_captures/`나 git에서 꺼낸다.

**정상 작업 흐름에 `npm run build`는 여전히 없다.** Fluid는 빌드 없이 파일만 고쳐 올리면
된다(§9). 빌드는 React 시안(`web/src/`)을 다시 볼 때만 필요하고, 그 산출물은
`/app/assets/*`로만 노출된다.

## 10. 함정

| 함정 | 내용 |
|---|---|
| **폰만 접속 안 됨** | `ERR_ADDRESS_UNREACHABLE`는 서버 문제가 **아니다** — 폰의 랜덤 MAC이 원인. 진단 순서는 [`08_troubleshooting.md`](08_troubleshooting.md) §2 |
| **`npm run build`** | §9-1 — 예전엔 Fluid를 덮었다. `web/app/` 분리로 해소(2026-09-09) |
| **CDN 금지** | 로봇은 LAN 전용이라 외부 폰트/스크립트 CDN에 못 나간다. Fluid는 시스템 폰트만 쓰므로 안전 |
| **`dist` push 중첩** | remote `web/dist`가 있는 채로 `adb push`하면 `dist/dist/`로 중첩된다. `rm -rf` 먼저 |
| 스트림만 안 보임 | `--idle-skip-draw`로 실행 중이고 뷰어가 0명이었다면 첫 JPEG가 늦게 뜬다 |

## 11. 관련 문서

- 서버 API·스키마: [`02_http_api_and_stats.md`](02_http_api_and_stats.md)
- 상위 설계 근거: [`../web/ARCHITECTURE.md`](../web/ARCHITECTURE.md)
- Fluid 제작 경위: [`history/2026-07-26_01`](history/2026-07-26_01_apple_design_ui_live_and_8080_unify.md)
- 종목 3버튼이 생긴 경위: [`history/2026-07-26_02`](history/2026-07-26_02_pushup_removed_overhead_lateral_added.md)

> **보관 계층 안내** — React 시안 6종(`registry.ts` 기준 `calm` · `rehab` · `session` ·
> `pulse` · `aurora` · `core`)과 서체·색 결정 근거는 [`../web/DESIGN.md`](../web/DESIGN.md)에
> 있다. 그 문서는 07-21 기준이라 "CALM 1종"으로 서술돼 오래됐고, `registry.ts` 주석도
> "CALM은 확정 UI가 아니라 검토 중인 후보"라고 적혀 있는데 **이 전제는 폐기됐다** —
> 확정 UI는 Fluid다. 두 문서 모두 갱신되지 않은 보관물로만 취급할 것.
