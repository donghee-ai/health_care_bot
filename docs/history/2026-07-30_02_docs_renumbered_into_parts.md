# 2026-07-30 — docs를 번호 체계(00~09)로 재편, 파트별 분할

## 시점

2026-07-30. 같은 날 [`2026-07-30_01`](2026-07-30_01_docs_readme_architecture_algorithms_web.md)에서
README를 최신화하고 상설 문서 3종(architecture/algorithms/web)을 만든 직후. 사용자 요청으로
**pose 라인(`unoq-pose/docs`)의 번호 체계 스타일**에 맞춰 docs 전체를 재편했다.

## 왜

세 가지 문제가 겹쳐 있었다.

1. **진입 순서가 없었다.** 파일명이 `HANDOFF.md`, `exercise_detection.md`,
   `reassembly_checklist.md`처럼 평면적이라 "무엇부터 읽어야 하는가"가 파일 목록에서 드러나지
   않았다. 번호가 붙으면 순서 자체가 정보가 된다.
2. **한 문서가 여러 주제를 안고 있었다.** `HANDOFF.md`는 하드웨어 값 + 실행법 + 함정표 +
   PTZ 튜닝 + 다음 할 일을 한꺼번에 담아 어느 절이 유효한지 매번 판단해야 했고, 실제로 07-26
   종목 개편 이후 §4·§5·§7이 stale해진 상태였다. `algorithms.md`도 PTZ와 운동 카운팅이라는
   별개 주제 두 개를 담고 있었다.
3. **중복.** `exercise_detection.md`(종목 설계)와 `algorithms.md` §2(카운팅 수식)가 같은 내용을
   다르게 서술하고 있었다.

pose 라인이 이미 `00_project_blueprint.md` ~ `09_*.md` + `history/` + `issues/` 구조를 쓰고
있었으므로, 같은 스타일로 맞추면 두 라인을 오갈 때 인지 비용도 줄어든다.

## 무엇을

### 1. 최종 구조 (docs/)

| # | 파일 | 담는 것 |
|---|---|---|
| 00 | `00_project_blueprint.md` | 청사진 — 목적·실측 현황·검증 상태·디렉토리·문서 지도·문서 규칙 |
| 01 | `01_architecture.md` | 프로세스/스레드, 파이프라인, 모듈 경계, 상태 소유권, 서보 경로, degrade |
| 02 | `02_http_api_and_stats.md` | HTTP 엔드포인트 계약, 제어권 모델, `stats.json` 전체 스키마, 필드 함정 |
| 03 | `03_algorithm_ptz_tracking.md` | PTZ 제어 법칙, 존 판정, 잠금, 손실 복구 사다리, 튜닝, 한계 |
| 04 | `04_algorithm_exercise.md` | 각도 정의, RepCounter 상태기계, 종목별 임계, 실패 모드, 푸시업 제외 근거 |
| 05 | `05_web_ui_fluid.md` | Fluid 화면·라이브 판정·제어권·조작·모션·배포 |
| 06 | `06_hardware_calibration.md` | 하드웨어 확정값, EEPROM 사고 이력, 재조립 5단계 절차, 벤치 도구 |
| 07 | `07_runbook.md` | 디바이스/PC 실행, 노드 확인, 배포(SSH/adb), 목업 개발, 종료 체크리스트 |
| 08 | `08_troubleshooting.md` | 증상 → 원인 색인 7개 분류 + `issues/` 전체 목록 |
| 09 | `09_performance_roadmap.md` | 성능 실측·병목 근거, 개선 레버, 다음 할 일 우선순위, 기각 목록 |

`history/`·`issues/`는 그대로 유지했다.

### 2. 파일 이동 매핑 (old → new)

| 이전 | 이후 | 방법 |
|---|---|---|
| `HANDOFF.md` | **분해** → `06`(§3 하드웨어) · `07`(§2 실행/환경) · `08`(§6 함정표) · `03`(§8 PTZ 튜닝) · `09`(다음 할 일) | `git mv` → `07_runbook.md` 후 재작성 |
| `exercise_detection.md` | `04_algorithm_exercise.md` (+ `algorithms.md` §2 카운팅 수식 병합) | `git mv` |
| `reassembly_checklist.md` | `06_hardware_calibration.md` (+ HANDOFF §3 하드웨어 값 병합) | `git mv` |
| `architecture.md` | `01_architecture.md` (+ API·스키마는 `02`로, 성능은 `09`로, 배포는 `07`로 분리) | rename |
| `algorithms.md` | `03_algorithm_ptz_tracking.md` (PTZ만) + `04`(운동) | rename + 분할 |
| `web.md` | `05_web_ui_fluid.md` | rename |
| (없음) | `00_project_blueprint.md` · `02_http_api_and_stats.md` · `08_troubleshooting.md` · `09_performance_roadmap.md` | 신규 |

**스텁을 남기지 않았다**(사용자 결정). 대신 아래 링크를 전부 갱신했다.

### 3. 스타일 통일 (pose 라인 규약)

- 파일명 `NN_snake_case_topic.md`
- 제목 다음에 **"본 문서는 … 정리합니다"** 목적 문단 — 대상 독자와 범위를 한 문단으로
- 절 번호는 **`## 0.` (한 눈에/요약)** 부터 시작, 하위는 **`### N-1.`** (점이 아니라 하이픈)
- 표 중심 서술, 상호 참조는 문서 번호로 (`[03](03_...md) §9`)

### 4. 링크 갱신

- `README.md` — 문서 지도를 00~09 표로 교체, 본문 참조 8곳 재지정
- `history/2026-07-26_04` · `2026-07-26_05` — `exercise_detection.md` 링크 → `04_...`
- `history/2026-07-26_05` — 옛 경로를 가리키는 안내 블록 추가(HANDOFF가 06/07/08로 분해됐음)
- `history/2026-07-30_01` — 본 재편으로 문서 위치가 바뀌었음을 명시 + 본 문서로 연결

## 원칙 — history는 고치지 않는다 (예외: 링크 경로)

`history/`·`issues/`는 그 시점의 기록이므로 **주장·수치·서술을 바꾸지 않았다.** 이번에 손댄
것은 **파일 이동으로 깨진 링크 경로**와, 옛 경로를 찾는 사람을 위한 **안내 블록 추가**뿐이다.
이 규칙 자체를 `00_project_blueprint.md` §7에 명문화했다.

## 검증

- **깨진 상대 링크 0건** — 새 문서 10개 + README + 수정한 history 3개의 모든 마크다운 링크를
  스크립트로 검사(존재 여부 확인).
- 코드(`src/`, `scripts/`, `docker/`)가 참조하는 docs 경로는 `history/`·`issues/`뿐이고, 이 두
  폴더는 움직이지 않았으므로 **코드 주석 링크는 영향 없음**을 grep으로 확인.
- 추적 파일 3개는 `git mv`로 옮겨 **rename으로 인식**된다(이력 보존).

## 남은 것

- `web/DESIGN.md`(07-21 기준, "CALM 1종"으로 서술 — 실제 6종)와 `APP_GUIDE.md`(React 시절,
  `--mode auto`·푸시업 언급)는 이번 재편 대상이 아니었다. `docs/00` §6-3에 "낡음"으로 표시만 해둠.
- `docker/Dockerfile`의 `CMD`가 아직 `--mode auto`다(손으로 `docker run`하면 즉시 종료).
  문서에는 기록했고(`01` §7-1, `08` §1) **코드는 미수정**.

## 관련

- 직전: [`2026-07-30_01`](2026-07-30_01_docs_readme_architecture_algorithms_web.md) — README 최신화 + 문서 3종 신설
- 참조 스타일: pose 라인 `unoq-pose/docs/00~09`
- 결과 진입점: [`00_project_blueprint.md`](../00_project_blueprint.md)
