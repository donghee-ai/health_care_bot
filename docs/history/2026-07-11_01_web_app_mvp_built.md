# 2026-07-11 — Health Care Bot Live PWA 최초 구현

## 시점

2026-07-11

## 사건

`APP_PLAN.md` + `health_care_bot_mvp_screen_plan.md`(화면 분리형 개정안) 기반으로
모바일 웹앱(PWA) 최초 구현 완료. 백엔드에 세션/제어권 API 신규 추가, 프론트엔드
Vite+React+TS 프로젝트를 처음부터 구축.

## 배경

기존 `http_server.py`는 `GET /`, `/stream.mjpg`, `/stats.json`만 제공하는
디버그 모니터링 전용이었다. 시연 관람객이 QR로 접속해 라이브 화면·운동
카운트를 보고, 운영자가 PTZ를 직접 조작하려면 정적 앱 서빙 + mutation API +
권한 분리가 필요했다.

## 결과

**백엔드** (`src/`)
- `app_state.py` 신규: 세션(시작/일시정지/재개/리셋/종료) + PIN 기반 운영자
  제어권 lock (60초 TTL + heartbeat 연장)
- `ptz_controller.py`: `manual_pan/tilt/center`, `set_auto_track` 추가 —
  자동 추적과 수동 조작이 충돌하지 않도록 분리
- `http_server.py`: `POST /api/ptz`, `/api/mode`, `/api/session/*`,
  `/api/control/*` + `/app` 정적 파일 서빙
- `main.py`: 위 상태 객체를 추론 루프에 연결, 앱에서 실시간 모드 변경 반영

**프론트엔드** (`web/`) — Vite + React + TypeScript
- 4화면(라이브/운동/카메라 제어/더보기) + 모바일 하단 네비 / 데스크톱
  사이드 네비, CSS 변수 기반 디자인 시스템(Dragonwing 톤)
- 추후(같은 날) 레퍼런스 이미지에 가까운 세이지그린 테마를 `data-theme`
  토글로 추가 — 컴포넌트 코드 변경 없이 CSS 변수 재정의만으로 구현
  (`web/ARCHITECTURE.md` §7)

**검증**: 카메라/모델 없이 `scripts/mock_serve.py`(신규, 실배포 미사용) +
Playwright로 뷰어/운영자 × 모바일/데스크톱 화면을 실제 브라우저에서
스크린샷 확인, 콘솔 에러 0건. PIN claim 직후 배지가 다음 폴링까지 늦게
갱신되는 문제를 발견해 낙관적 로컬 상태로 즉시 수정.

실제 UNO Q 디바이스(`unoq-korea01`, adb serial `1204329696`)에도 배포해
컨테이너 기동 로그로 `/app` 서빙 확인 (상세: `2026-07-11_02_device_deploy_camera_not_detected.md`).

## 다음 단계

- USB 카메라 재연결 후 실제 라이브 스트림 e2e 확인
- PTZ 시리얼(`/dev/ttyACM0`) 연결 후 수동 조작 실기 검증
- 네트워크 의존성 완화책(mDNS/핫스팟)은 시연 환경 확정 후 착수
  (`web/ARCHITECTURE.md` §8)
