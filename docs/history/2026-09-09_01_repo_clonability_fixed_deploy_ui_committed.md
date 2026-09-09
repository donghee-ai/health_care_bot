# 2026-09-09 리포 클론 가능성 복구 — 배포 UI 커밋 · Dockerfile CMD · 문서 정합

> 앞선 세션([`2026-09-08_01`](2026-09-08_01_docs_synced_to_runtime_verified_on_device.md))에서
> 문서를 실기 런타임에 맞췄는데, 그때 **"리포 안"만 맞췄고 "리포 밖"이 남아 있었다.**
> 이 문서는 그 나머지를 정리한 기록이다.

---

## 1. 한 줄 요약

**처음 보는 사람이 clone해서 `/app`까지 도달하지 못하는 상태**였다. 배포 UI가 gitignore된
`web/dist/`에만 있었기 때문이다. 배포본을 커밋되는 `web/app/`으로 옮기고 서버가
`web/app` → `web/dist` 순으로 찾게 했다. 덤으로 `docker run` 직접 호출이 즉사하던
Dockerfile CMD, 실행 불가였던 `mock_serve.py`, 실제와 어긋난 README 폴더 트리를 고쳤다.

---

## 2. 무엇이 문제였나

### 2-1. 배포 UI가 리포에 아예 없었다 (가장 큰 문제)

README §4 · [`00`](../00_project_blueprint.md) · [`05`](../05_web_ui_fluid.md) §9가
`web/dist/index.html`을 **"현재 `/app`으로 서빙되는 확정 UI, 유일한 최신본"** 이라고
못박고 있었는데, `web/.gitignore`의 `dist` 규칙 때문에 그 파일은 **커밋 이력에 한 번도
없었다**(`git log -- web/dist` → 없음).

결과:

- clone하면 `/app`이 `503 {"error": "web_not_built"}`.
- 안내대로 `npm run build`를 하면 `web/src`의 React 시안이 나온다 — 문서가 말하는
  "Fluid"가 아니다.
- README §8이 "`npm run build`하면 Fluid가 덮인다"고 경고하는데, **클론 환경엔 덮일
  Fluid 자체가 없었다.** 문서가 서술하는 시대와 코드의 시대가 달랐다.

### 2-2. Dockerfile CMD가 죽는 인자를 들고 있었다

`docker/Dockerfile`의 `CMD`가 `--mode auto`인데 argparse choices는
`squat/overhead/lateral/guard`([`src/main.py:154`](../../src/main.py))다.
`docker run`을 직접 부르면 **exit 2로 즉사**한다. `docker/run.sh`가 `--mode squat`로
덮어써서 가려져 있었을 뿐이다. `--rm`이라 `docker logs`에도 안 남는다.

README §8에 "argparse ↔ run.sh 동기화"라는 함정 항목이 **이미 있었는데도** Dockerfile은
2026-07-26 pushup 제거 때 같이 고쳐지지 않았다.

### 2-3. `scripts/mock_serve.py`가 실행 불가였다

pushup 제거(2026-07-26) 이후 갱신되지 않아 세 군데가 죽어 있었다:

- `from exercise_counter import ... PushupCounter` → **ImportError** (import 단계에서 즉사)
- `init_app(..., pushup_c=...)` → TypeError (시그니처가 `overhead_c`/`lateral_c`로 바뀜)
- `app_state.set_mode("auto")` → `{"ok": false, "error": "invalid_mode"}`

README §4에는 정상 도구로 올라가 있었다.

### 2-4. 문서 ↔ 실제 불일치

| README 기재 | 실제 |
|---|---|
| `stl/` | `3d_model/` (하위 `3mf`·`source`·`stl`·`validation`·`preview`) |
| 복원점 3개 | `backup/` 5개 |
| 모델은 git 미포함 (§10, §3.4) | `models/movenet_thunder_int8.tflite` 7.1 MB **커밋되어 있음** |
| (누락) | `APP_PLAN.md`, `health_care_bot_mvp_screen_plan.md`, `app_reference.png`, `APP_GUIDE.md` |
| §10 제목 "모델 / 라이센스" | 라이센스 문장 없음 · LICENSE 파일 없음 |

`web/README.md`는 손대지 않은 Vite 보일러플레이트 그대로였다.

---

## 3. 어떻게 고쳤나

### 3-1. 배포본을 `web/app/`으로 (핵심)

`web/dist/index.html`(49,022 B)은 **완전 자체포함**이다 — 외부 JS·CSS·`@font-face`가
하나도 없고 시스템 폰트만 쓴다(확인함). 그래서 파일 하나만 옮기면 끝난다.

```
web/app/index.html      ← 커밋. 배포본. 여기를 직접 고친다
web/dist/               ← 그대로 gitignore. React 시안 빌드 산출물일 뿐
```

`src/http_server.py`의 `_WEB_DIST` 단일 경로를 `_WEB_DIRS` 튜플로 바꾸고,
`_resolve_static()`이 **`web/app` → `web/dist` 순으로** 찾도록 했다.

이 순서가 핵심이다:

- **clone 직후 빌드 없이 `/app`이 뜬다** — 503 소멸.
- **`npm run build`가 배포 UI를 못 덮는다** — dist를 덮어도 `/app`은 `web/app`을 본다.
  README §8 · [`05`](../05_web_ui_fluid.md) §9-1의 함정이 코드 레벨에서 사라졌다.
- **아직 옮기지 않은 디바이스도 그대로 동작한다** — `web/app`이 없으면 기존
  `web/dist/index.html`로 폴백되므로, 배포 전에도 화면이 바뀌지 않는다.
- `/app/assets/*`(React 시안 자산)는 계속 `web/dist`에서 나온다.

경로 탈출 차단(`resolve()` + `relative_to()` → 403)은 디렉터리마다 각각 적용된다.

### 3-2. Dockerfile CMD

`--mode auto` → `--mode squat` (run.sh가 넘기는 값과 동일). 헤더 주석의 `pushup`도
`squat / overhead / lateral / guard`로 갱신.

### 3-3. 운영자 PIN을 환경변수로

PIN이 `src/app_state.py`에 하드코딩(`1234`)되어 있어 README의 "시연 전 교체 권장"을
따르려면 **코드를 고치는 수밖에 없었다.** 환경변수 오버라이드를 넣었다:

```python
_DEFAULT_OPERATOR_PIN = "1234"
_operator_pin = os.environ.get("HCB_OPERATOR_PIN", "").strip() or _DEFAULT_OPERATOR_PIN
```

`docker/run.sh`가 `HCB_OPERATOR_PIN`이 설정된 경우에만 `-e`로 전달한다:

```bash
HCB_OPERATOR_PIN=8317 bash docker/run.sh
```

**기본값은 그대로 `1234`** 이므로 지금까지의 동작은 변하지 않는다.
(이건 인증이 아니라 오조작 방지다 — [`02`](../02_http_api_and_stats.md) §6 그대로.)

### 3-4. 나머지

- `scripts/mock_serve.py`: `OverheadPressCounter`/`LateralRaiseCounter`로 교체,
  `init_app` 시그니처 정정, `set_mode("squat")`, live 상태에 `overhead`/`lateral` 추가.
  **실제로 띄워서** `/stats.json`과 `/app`(49,022 B) 응답까지 확인함.
- `src/exercise_counter.py` 모듈 docstring의 `pushup (팔꿈치 각도)` → 실제 종목으로.
- `web/README.md`: Vite 보일러플레이트 → 배포본/시안/빌드산출물 3계층 설명으로 교체.
- README §3.4를 "보통 불필요"로. 모델은 이미 커밋되어 있다.
- README 폴더 트리를 실제와 일치시킴(§2-4 표 전부).
- README §10 제목 "모델 / 라이센스" → **"모델 / 제3자 자산"**. 라이센스는 아직 정하지
  않았으므로 "LICENSE 없음 = 저작권 유보"만 명시했다. **LICENSE 파일은 여전히 없다.**
- `README.md` §3.1의 `# 키 등록됨, 비번 없음` 주석 제거(공개 리포).

---

## 4. 검증

| 확인 | 방법 | 결과 |
|---|---|---|
| `/app` = Fluid | 로컬 서버 기동 후 GET | 200, 49,022 B (`web/app`에서) |
| **clone 직후 시나리오** | `_WEB_DIRS`에서 dist 제거 후 GET | **200, 49,022 B** (이전엔 503) |
| 기존 디바이스 폴백 | `web/app` 없이 dist만 | 200 (동작 유지) |
| SPA 폴백 | `/app/nope-route` | 200, index.html |
| React 자산 | `/app/assets/index-CvZFNyLL.js` | 200, `application/javascript` |
| 경로 탈출 | `/app/../../src/http_server.py` | **403** |
| 둘 다 없음 | 가짜 경로 2개 | 503 `web_not_built` |
| PIN 기본/오버라이드/공백 | import 후 값 확인 | `1234` / `8317` / `1234` |
| `run.sh` 문법 | `bash -n` | OK |
| `mock_serve.py` | 실제 기동 + HTTP 확인 | OK |

**실기(UNO Q)에서는 아직 확인하지 않았다.** 디바이스는 `web/app`이 없는 상태이므로
폴백 경로를 타고 지금과 동일하게 뜬다 — 즉 배포 전에도 안전하다. 배포하려면:

```bash
scp web/app/index.html arduino@192.168.0.50:~/health_care_bot/web/app/index.html
```

---

## 5. 남은 것

- **LICENSE 파일** — 라이센스 종류가 정해지지 않아 이번엔 보류했다. §10에 "미정"만 적었다.
- **테스트·CI 없음** — `scripts/test_st3215_serial.py`는 하드웨어 수동 도구다.
  최소한 `/app` 서빙·`app_state` 전이 정도는 CI로 묶을 여지가 있다.
- 디바이스의 낡은 `web/dist/index.html`은 폴백용으로 남아도 무해하지만, `web/app`을
  배포한 뒤에는 헷갈리지 않게 지워도 된다.
- README §3.2·`08`에 남은 `192.168.0.50`은 사설 IP라 그대로 뒀다.

---

## 6. 관련 문서

- 서빙 우선순위: [`02_http_api_and_stats.md`](../02_http_api_and_stats.md) §5
- 배포 절차: [`05_web_ui_fluid.md`](../05_web_ui_fluid.md) §9, §9-1
- 폴더 구조: [`00_project_blueprint.md`](../00_project_blueprint.md) §5
- 앞 세션: [`2026-09-08_01`](2026-09-08_01_docs_synced_to_runtime_verified_on_device.md)
