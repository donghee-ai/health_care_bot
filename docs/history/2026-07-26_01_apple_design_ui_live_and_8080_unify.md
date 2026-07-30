# 2026-07-26 — 애플 디자인 라이브 UI 신규 + 8080 통일 + 모바일 접속 디버그

## 시점

2026-07-26. Emil Kowalski의 Apple 디자인 스킬을 설치한 뒤, 기존 웹앱과 별개로
라이브 화면 시안을 새로 만들고 로봇 실카메라에 연동, 최종적으로 `:8080/app`으로
통일했다.

## 한 일

### 1. Apple 디자인 스킬 설치

`npx skills@latest add emilkowalski/skills`로 전역(`~/.claude/skills`) 설치:
`apple-design`, `emil-design-eng`, `review-animations`, `improve-animations`,
`animation-vocabulary` (+ 저장소엔 `find-animation-opportunities`,
`pick-ui-library`도 있음). `review-animations`는 `disable-model-invocation:true`라
사용자가 `/review-animations`로 **직접 호출할 때만** 동작. (`frontend-design`은
플러그인 마켓플레이스에 있으나 이 CLI 세션엔 미로드 — SKILL.md 내용으로 적용.)

### 2. 라이브 화면 시안 2종 신규 (`design_demos/`)

- **`live_frontend-design.html` — "Field Optics"**: 로봇의 *시선/PTZ 추적*을 정체성으로,
  광학 계기(레티클·FOV·mono 텔레메트리) 컨셉. 카메라 피드 듀오톤 처리(리스크).
  팔레트: 웜 본 + 딥 스프루스 + 형광 샤르트뢰즈 (Toss 보라/파랑 기본값·AI 클리셰 회피).
- **`live_apple-design.html` — "Fluid"**: apple-design 스킬 원칙 구현 — 직접 만든
  스프링 엔진(감쇠/response), 액티비티 링, 러버밴딩·속도 핸드오프·관성 투영,
  reduced-motion. **이후 이게 메인이 됨.**

### 3. 로봇 실카메라 연동

두 페이지 모두 `location.hostname:8080`의 `/stats.json`을 폴링해 잡히면 **라이브 모드**:
히어로=`/stream.mjpg`(스켈레톤 baked-in), 레티클=실제 `person_center_norm`,
링/모드/PTZ/피드백=실제 stats. 없으면 `getUserMedia` 데모 폴백. `stats.json`은
`Access-Control-Allow-Origin:*`라 크로스오리진 OK.

### 4. SSH 배포 + 공유 제어권

- 파일을 디바이스 `~/health_care_bot/design_demos/`로 전송, `python -m http.server 8777`
  (0.0.0.0) 서빙.
- **공유 제어권**: 모든 클라이언트가 같은 `client_id="hcb-demo"` + PIN `1234`로
  제어권을 공유 → **누구나 조종**(마지막 명령 우선, 격리 없음). 조이스틱이 실제
  `/api/ptz`로 서보 구동, 운동모드/auto_track도 실제 API.

### 5. Fluid 반복 개선 (최종 형태)

- 운동 세그먼트 **Auto 제거 → Squat / Push-up(비활성)**.
- PTZ 카드 **자동추적 ⇄ 직접조작** 토글: 자동=**텔레메트리**(FPS·추론 loop ms·CPU 온도·RAM·CPU%),
  수동=**조이스틱**(실서보). 실제 `ptz.auto_track_enabled` 반영.
- 상단 **설정 기어(⚙) → QR 모달**로 모바일 접속(자체 인라인 QR SVG, segno 생성).
- **컴퓨터/모바일 분리 레이아웃**: 폰 = 100dvh 한 화면(카메라 flex 축소), 컴퓨터(≥820px)
  = 단일 세로 컬럼 **큰 카메라 위 + 정보 패널 아래**(카메라 안 줄임, 스크롤).
- `onLive` 전체 try/catch + 방어적 필드 접근(한 프레임 이상해도 프리징 방지).

### 6. 8080 통일 + run.sh에 카메라 굽기 (영구화)

- **`web/dist/index.html` = 애플 페이지**로 교체 → `/app`이 애플 디자인. 기존 stock은
  `web/dist/index.html.stock.bak` 백업. 로컬 레포도 동일하게 맞춤. QR도 `:8080/app`으로 재생성.
  이제 **:8777 불필요, 포트 하나(8080)로 통일.**
- **`docker/run.sh`에 USB 카메라 자동탐색 추가**: `/sys/class/video4linux/*/name`에서
  이름에 `Camera` 있는 노드 선택(Venus 코덱 회피), 기본 `/dev/video2`. → **`bash docker/run.sh`
  만으로 카메라 2번** 자동 사용(부팅마다 노드 바뀌어도 자동).

### 7. 모바일 접속 디버그

폰 접속 실패를 추적 → **폰 랜덤 MAC**이 원인으로 판명(별도 이슈
[`2026-07-26_01`](../issues/2026-07-26_01_mobile_web_access_fails_random_mac.md)).

## 검증

- `bash docker/run.sh`(env 없이) → 로그 `camera : /dev/video2 640x480`, `actual : 640x480`(정상 오픈).
- `/app is apple: True`, `stats.json` 라이브 fps ~10, `ptz in_frame`. PC 접속 HTTP 200.
- 두 시안 JS `node --check` 통과.

## 주의 / 되돌리기

- **애플 페이지는 자체 포함 정적 HTML** → React `npm run build` 대상 아님. 빌드하면
  `web/dist/index.html`이 stock 앱으로 덮이므로, 그때 애플로 되돌리려면
  `design_demos/live_apple-design.html`(또는 QR을 :8080/app로 맞춘 빌드본)을 다시 배포.
  stock 복원: `web/dist/index.html.stock.bak`.
- 07-20 웹 백업(`backup/web_2026-07-20_pre_redesign/`)으로 롤백을 시도했었으나, 접속 실패
  원인이 프론트가 아니라 폰이었으므로 롤백은 원복했다(web/dist는 다시 최신/애플).

## 관련

- 시안 원본: `design_demos/live_apple-design.html`, `live_frontend-design.html`
- 이슈: [`issues/2026-07-26_01_mobile_web_access_fails_random_mac.md`](../issues/2026-07-26_01_mobile_web_access_fails_random_mac.md)
- 실행: `cd ~/health_care_bot && bash docker/run.sh` → `http://192.168.0.45:8080/app`
