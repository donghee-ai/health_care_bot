# `web/` — 두 계층

이 디렉터리에는 **성격이 다른 두 가지**가 같이 있다. 헷갈리기 쉬우므로 먼저 구분한다.

| | 경로 | 정체 | 서빙됨? | git |
|---|---|---|---|---|
| **배포본** | `app/index.html` | 자체포함 정적 HTML 1개 (애플 "Fluid") | **예 — `/app`** | 커밋됨 |
| 보관 계층 | `src/` | Vite + React PWA 시안 6종 (CALM/PULSE/AURORA/CORE/CARE/LIVE) | 아니오 | 커밋됨 |
| 빌드 산출물 | `dist/` | 위 시안을 `npm run build`한 결과 | `/app/assets/*`만 | gitignore |

## 배포본 (`app/index.html`)

로봇의 `/app`이 보여주는 화면이다. **HTML·CSS·JS가 전부 한 파일에 인라인**되어 있고
외부 폰트·CDN·번들러를 쓰지 않는다 (로봇은 LAN 전용이라 외부에 나갈 수 없다).

- 고칠 때는 **이 파일을 직접 고친다.** 빌드 단계가 없다.
- 빌드가 없다는 건 문법 오류를 잡아줄 단계도 없다는 뜻이다. 올리기 전에 `<script>`
  블록만 떼어 `node --check`로 확인하거나 최소한 브라우저 콘솔을 한 번 열 것.
- 배포: `scp web/app/index.html <device>:~/health_care_bot/web/app/index.html`
  (`http_server`가 매 요청마다 디스크를 읽으므로 컨테이너 재시작 불필요)

화면 구성·조작·배포 절차: [`../docs/05_web_ui_fluid.md`](../docs/05_web_ui_fluid.md)

## React 시안 (`src/`)

2026-07 초 웹앱 방향을 잡을 때 만든 시안 6종이다. **현재 런타임에 쓰이지 않는다.**
다시 볼 일이 생겼을 때만:

```bash
cd web
npm install
npm run build     # -> web/dist/ (배포본을 덮지 않는다)
npm run dev       # 개발 서버. 백엔드는 scripts/mock_serve.py 로 대신할 수 있다
#   VITE_BACKEND_URL=http://localhost:8090 npm run dev
```

> `npm run build`는 **배포본을 건드리지 않는다.** 서버가 `web/app` → `web/dist`
> 순으로 찾기 때문이다. (2026-09-09 이전에는 배포본이 `dist/index.html`에 있어서
> 빌드하면 덮이는 함정이 있었다.)

설계 근거는 [`ARCHITECTURE.md`](ARCHITECTURE.md), 서체·색 결정은 [`DESIGN.md`](DESIGN.md).

## 폰트

`public/fonts/`의 Pretendard 서브셋은 `scripts/subset_pretendard.py`로 생성한다
(원본은 `fonts-src/`). 배포본은 시스템 폰트만 쓰므로 이 폰트들은 React 시안 전용이다.
