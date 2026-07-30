# Health Care Bot Live — 아키텍처 & 설계 근거

이 문서는 "무엇을 만들었나"가 아니라 **"왜 이렇게 만들었나"**를 남긴다. 구현
상세와 실행 방법은 [`APP_GUIDE.md`](../APP_GUIDE.md), 기획 원안은
[`APP_PLAN.md`](../APP_PLAN.md) / [`health_care_bot_mvp_screen_plan.md`](../health_care_bot_mvp_screen_plan.md)
참고.

## 1. 전체 데이터 흐름

```
[React SPA (정적 빌드, web/dist)]
        │  fetch('/stats.json')  500ms polling
        │  <img src="/stream.mjpg">
        │  fetch('/api/*', POST)
        ↓
[src/http_server.py — Python stdlib http.server]
        │  기존 추론 루프(main.py)가 update_live_state()로 채워주는
        │  전역 상태를 그대로 읽어서 JSON/정적파일/멀티파트로 응답
        ↓
[src/app_state.py]  세션 상태 + PIN 제어권 lock (in-memory, DB 없음)
[src/ptz_controller.py]  manual_pan/tilt/center + auto_track 토글
```

프론트/백엔드는 별도 서버가 아니라 **하나의 Python 프로세스**가 전부
서빙한다. UNO Q에는 컨테이너 하나, 프로세스 하나만 뜬다.

## 2. 왜 네이티브 앱이 아니라 PWA(모바일 웹앱)인가

- 시연 목표가 "QR 스캔 후 3초 안에 접속"이다. 네이티브 앱은 설치 과정 자체가
  이 목표와 충돌한다.
- 이미 `stream.mjpg` + `stats.json`을 제공하는 HTTP 서버가 있었다 —
  네이티브로 가면 이 자산을 버리고 새 프로토콜을 짜야 한다.
- 관람객/운영자 둘 다 브라우저만 있으면 되므로 Android/iOS 배포 파이프라인이
  필요 없다.

## 3. 왜 Bluetooth가 아니라 WiFi/HTTP인가

"같은 네트워크에 있어야 한다"는 제약을 없애려고 Bluetooth 전환을 검토했지만
기각했다:

1. **영상 스트리밍이 핵심 기능인데 대역폭이 안 나온다.** BLE는 MJPEG를 실어
   나르기엔 너무 느리고, Bluetooth Classic(SPP)은 그나마 낫지만 브라우저
   API로 접근할 수 없어 네이티브 앱을 새로 짜야 한다 — PWA로 간 이유(§2)와
   정면으로 충돌.
2. **iOS Safari가 Web Bluetooth를 아예 지원하지 않는다.** "QR 스캔 후 설치 없이
   접속"이라는 핵심 목표가 아이폰 사용자 전원에게서 깨진다.
3. **애초에 병목을 안 풀어준다.** 네트워크 의존성 문제의 실체는 "영상을 어떻게
   보여주냐"이지 "명령을 어떻게 보내냐"가 아니다. PTZ 명령 같은 저대역폭
   채널만 Bluetooth로 뺀다 해도 영상은 여전히 WiFi가 필요해서 원래 고민이
   그대로 남는다.

네트워크 의존성 자체는 인정하는 제약이고, 완화책은 §9에 정리.

## 4. 왜 Node/FastAPI가 아니라 기존 `http.server` 확장인가 (1차 구현)

- `docker/Dockerfile`에 Node가 없다 — 프론트 빌드는 호스트(개발 PC 또는
  디바이스 콘솔)에서 한 번 하고, 컨테이너는 `web/dist` 정적 파일만 볼륨
  마운트로 읽는다. 런타임에 Node/Vite가 디바이스에서 도는 일은 없다.
- 기존 `http_server.py`가 이미 MJPEG + JSON을 서빙하고 있었다. API 몇 개
  (`POST /api/*`) 추가하는 것으로 충분한데 FastAPI/uvicorn을 새로 얹으면
  의존성만 늘어난다. `APP_PLAN.md` §8.2도 1차는 `http.server` 유지, 2차에
  FastAPI 전환을 권장했다.
- 결과적으로 웹앱 레이어가 추가한 런타임 비용은 정적 파일 응답 + 저빈도
  JSON API 라우팅뿐이다 — 카메라 캡처/추론/인코딩 같은 무거운 작업은
  웹앱 이전과 완전히 동일하다.

## 5. 왜 WebSocket/SSE가 아니라 500ms polling인가 (1차 구현)

- 상태 갱신 목표가 250–500ms면 충분하다고 `APP_PLAN.md` §6.1에 이미 정의돼
  있다 — 실시간 커넥션이 주는 이점(수 ms 단위 지연 감소)이 이 앱의 요구사항
  대비 과설계다.
- `http.server`는 커넥션을 오래 붙잡는 WebSocket과 궁합이 안 좋다
  (`ThreadingMixIn` 기반이라 스레드 하나가 커넥션 하나를 통째로 점유).
  polling(JSON API 계층)은 요청-응답이 즉시 끝나 스레드 회전이 빠르다.
- 2차 구현(FastAPI 전환 시)에서 SSE/WebSocket으로 옮기는 걸 `APP_PLAN.md`가
  이미 로드맵에 넣어뒀다 — 지금 안 하는 이유가 "못 해서"가 아니라 "아직
  필요 없어서".
- 다만 이건 `/stats.json`·`/api/*` 같은 짧은 요청-응답 계층에만 해당하는
  이야기다. `/stream.mjpg`는 정의상 커넥션을 계속 붙잡는 스트림이라 이미
  스레드 하나를 영구 점유하고 있고, 이건 polling을 쓰든 WebSocket을 쓰든
  똑같이 존재하는 비용이다. 뷰어가 많아졌을 때 이게 실제로 버티는지는
  검증 전 — §9 참고.

## 6. 왜 풀 인증이 아니라 PIN 기반 제어권 lock인가

- 배포 환경이 로컬 LAN 전용으로 명시돼 있다 (`README.md`, `APP_PLAN.md` §11) —
  외부 인터넷에 노출되지 않는다는 전제.
- 위협 모델이 "악의적 공격자"가 아니라 "관람객이 실수로 다른 사람이 조작
  중인 PTZ를 건드리는 것" 정도다. PIN + 60초 lock + heartbeat 연장이면
  충분하고, 세션/유저 관리, 비밀번호 해싱, JWT 같은 걸 넣는 건 과설계.
- 상태도 DB 없이 `app_state.py`의 in-memory dict + `threading.Lock` 하나로
  충분 — 디바이스가 재시작되면 lock도 같이 초기화되는 게 오히려 안전하다
  (좀비 lock이 안 남음).
- 단, 이 lock이 푸는 건 "PTZ를 누가 조작하냐"는 충돌뿐이다. "여러 명이
  동시에 접속했을 때 서버가 부하를 버티는가"라는 더 넓은 다중 접속 문제는
  아직 별개로 미해결 상태다 — §9 참고.

## 7. 왜 CSS 변수 테마가 아니라 시안별 독립 폴더인가 (2026-07-20 변경)

> 이전에는 `:root`의 CSS 변수를 치환하는 단일 테마 시스템이었다
> (`index.css` + `hooks/useTheme.ts`). 2026-07-20 재설계에서 이 구조를
> 버렸다. 설계 근거 전체는 [`DESIGN.md`](./DESIGN.md).

변수 치환은 **같은 레이아웃에 색만 바꿀 때** 유지보수 비용이 0에 가깝다.
하지만 이번 요구는 "완전히 다른 느낌의 시안 4개"였고, 그건 색 문제가
아니라 **정보 구조·밀도·조판이 통째로 다른 문제**였다.

- INSTRUMENT는 헤어라인 격자에 수치를 빽빽이 깔고, CALM은 링 하나에
  숫자 한 개만 놓는다. 같은 마크업에 변수만 바꿔서 나올 수 있는 차이가
  아니다.
- 변수로 억지로 묶었다면 모든 컴포넌트가 4가지 분기를 품게 되고,
  시안 하나를 고치다 나머지 셋이 깨지는 구조가 된다.

그래서 **시안마다 `.tsx` + `.css`를 통째로 소유**하고 서로 아무것도
공유하지 않게 했다. lazy로 나뉘어 있어 보고 있는 시안의 CSS만 로딩된다 —
네 벌의 CSS가 한꺼번에 들어와 서로 덮어쓰는 사고를 구조적으로 막는다.

공유하는 건 **데이터와 동작뿐**이다. 훅(`useStats`, `useMjpeg`,
`useRepPulse`, `useSeries`, `usePressRepeat`)은 값을 계산하고 상태를
관리할 뿐 마크업을 만들지 않는다. 서버 API 계약도 그대로다.

대가는 CSS 중복이다. 시안을 하나로 확정하고 나면 나머지 셋을 지우면서
회수된다 — 비교 단계에서만 지불하는 비용으로 봤다.

## 7-1. 폰트를 왜 self-host 하는가

로봇은 LAN 전용이라 **구글 폰트 CDN에 나갈 수 없다.** CDN을 쓰면
시연장에서 폰트만 통째로 안 뜨는 사고가 난다.

Pretendard 원본 2.0MB는 "QR 스캔 후 3초"(§2) 목표와 충돌해서,
`scripts/subset_pretendard.py`로 unicode-range 조각을 만든다.
소스에 실제로 쓰는 글자를 모은 우선 조각(`kr-core`)을 맨 앞에 두고
나머지는 안전망으로 뒤에 남긴다 — 모든 글자가 어딘가에는 있으므로
두부(□)가 원천적으로 불가능하다. 실측 226~346 KB / 3~4 요청.

코드포인트 순으로만 쪼갰다가 실패한 기록:
[`docs/issues/2026-07-20_01`](../docs/issues/2026-07-20_01_unicode_range_chunking_by_codepoint_is_useless.md)

## 8. 왜 캡처 스레드를 분리했는가 — 지연(latency)과 처리량(FPS)은 다른 문제

`src/main.py::FrameGrabber`(2026-07-15 추가)는 카메라를 별도 스레드에서
계속 읽어 최신 프레임 1장만 보관하고, 추론 루프는 그 최신 프레임만
가져다 쓴다. 이 수정을 이해하려면 **지연**과 **FPS(처리량)**를 구분해야
한다 — 실측 검증에서 이 둘이 서로 다르게 움직이는 걸 직접 확인했다
(`docs/history/2026-07-15_01_framegrabber_verified_latency_fixed_fps_unchanged.md`).

- **문제였던 것 (지연)**: 카메라가 캡처하는 속도(예: ~33ms/frame)가 추론
  루프 속도(예: ~90ms/frame)보다 빠르면, `cap.read()`를 메인 루프에서
  직접 부를 경우 안 읽힌 프레임이 드라이버 버퍼에 계속 쌓인다.
  `cv2.CAP_PROP_BUFFERSIZE=1`을 걸어놔도 V4L2/UVC 드라이버에 따라 무시되는
  경우가 흔해 안전장치가 못 된다 — 그 결과 화면은 매끄럽게 재생되지만
  실시간보다 계속 뒤처진 프레임을 보여주는(그리고 계속 더 뒤처지는)
  증상이 났다.
- **FrameGrabber가 고친 것**: 큐가 아니라 "최신 프레임 1장 덮어쓰기"
  방식으로 바꿔서, 처리되는 프레임의 나이(age)가 항상 "루프 1회분"으로
  고정되고 더 이상 누적되지 않는다. 사용자 실측 결과 "실시간성이 있다"로
  체감 확인됨.
- **FrameGrabber가 안 고치는 것 (FPS)**: 추론(MoveNet) + pose draw + JPEG
  인코딩 자체의 처리 속도는 그대로다. 이 파이프라인이 루프당 ~90ms
  걸리면, 초당 실제로 처리·전송되는 distinct 프레임 수(=`/stats.json`의
  `fps`)는 여전히 ~11fps 근처다. 배포 후 실측에서 `fps`가 수정 전후로
  **10.8 ±4로 동일**하게 나온 것 자체가, 이 수정이 의도대로 지연만
  고치고 처리량은 안 건드렸다는 증거다 — 회귀가 아니라 예상된 결과.
- **FPS(처리량) 자체를 올리려면** 별도 작업이 필요하다 — 해상도 축소,
  추론 스레드/딜리게이트 튜닝, 인코딩 품질 조정 등. 현재 요구사항 밖이라
  미착수.

## 9. 알려진 제약 & 완화책

| 제약 | 이유 | 완화책 (미구현, 필요 시 추가) |
|---|---|---|
| 같은 WiFi/네트워크에 있어야 접속 가능 | §3 참고 — Bluetooth로도 안 풀리는 문제라 WiFi 유지 | `healthbot.local` mDNS(avahi), 또는 UNO Q 자체 핫스팟(hostapd) — `APP_PLAN.md` §5에 설계는 있으나 코드 미구현 |
| PIN이 평문 하드코딩(`app_state.py::_operator_pin`) | 로컬 LAN 전용 전제, 시연용 최소 마찰 | 시연 전 값 교체 필수. 외부 노출 시나리오가 생기면 `.env` 분리 필요 |
| 500ms polling → 순간 상태는 최대 500ms 지연 | §5 참고, 현재 요구사항엔 충분 | FastAPI + SSE/WebSocket 전환 (`APP_PLAN.md` Phase 3) |
| 세션/제어권 상태가 프로세스 재시작 시 소실 | in-memory, DB 없음 (§6) | 시연 성격상 허용 범위로 판단. 영속화 필요해지면 SQLite 검토 |
| PTZ 직접 제어 지연 목표치(API 응답 100ms, 실제 서보 movement 시작 100–300ms)가 아직 미검증 | 실제 서보가 디바이스에 체결된 적이 없어 `APP_PLAN.md` §6.2/§14의 목표값을 그대로 문서화만 해둔 상태 — 실측 아님 | **추후 모터 실제 체결 후 재측정해서 이 문서와 `APP_PLAN.md` 수치를 갱신할 예정** |
| 다중 동시 접속 처리가 아직 해결되지 않음 — 여러 관람객·여러 운영자가 한꺼번에 붙었을 때의 서버 부하/안정성이 미검증 | `http.server`의 `ThreadingMixIn`이 커넥션(특히 `/stream.mjpg`)마다 스레드를 하나씩 점유하는 구조라 대량 동시 접속 시 성능이 실측된 적 없음 (`APP_PLAN.md` §14 "5명 이상 동시 접속 시 서버 유지" 목표는 아직 검증 전) | **일단은 PTZ 제어권만 PIN 기반 lock으로 운영자 1명에게 위임**(§6)해 "여러 명이 동시에 장비를 조작"하는 충돌만 막아둔 상태 — 동시 접속자 수 자체를 제한하거나 서버 부하를 검증하는 작업은 아직 안 함 |
| FPS(처리량)이 낮음(~10.8 ±4) | §8 참고 — 추론+draw+encode 파이프라인 자체 속도 한계, FrameGrabber는 지연만 고침 | 해상도 축소, 추론 스레드/딜리게이트 튜닝, 인코딩 품질 조정 (미구현) |

## 10. 관련 문서

- **디자인 시안 4종 & 서체·색 결정 근거: [`DESIGN.md`](./DESIGN.md)**
- 실행 방법: [`APP_GUIDE.md`](../APP_GUIDE.md)
- 기획 원안: [`APP_PLAN.md`](../APP_PLAN.md), [`health_care_bot_mvp_screen_plan.md`](../health_care_bot_mvp_screen_plan.md)
- 로봇 본체 아키텍처(추론 루프/PTZ 하드웨어): [`README.md`](../README.md)
- 의사결정 히스토리: [`docs/history/`](../docs/history/)
