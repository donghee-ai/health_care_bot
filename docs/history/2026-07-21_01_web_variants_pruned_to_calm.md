# 2026-07-21 — 웹 시안 4종 → CALM 1종(후보)으로 정리

## 시점

2026-07-21. 전날 만든 디자인 시안 4종
([`2026-07-20_01`](2026-07-20_01_web_redesign_four_variants.md))을 검토한 뒤.

## 사건

시안 4종 중 **CALM만 후보로 남기고 INSTRUMENT·ALMANAC·STADIUM은
삭제**했다. CALM도 확정이 아니라 **후보 상태**로 둔다 — 백업 유지,
문서에 후보로 표기, 프로덕션 승격(원본 대체·백업 삭제) 안 함.

## 삭제한 것

- 폴더: `src/versions/{instrument,almanac,stadium}/` (각 `.tsx` + `.css`)
- 훅: `src/hooks/useSeries.ts` — 스파크라인용이었고 INSTRUMENT·STADIUM만
  쓰던 것이라 두 시안 삭제로 죽은 코드가 됨
- 폰트: `spline-sans-mono-var.woff2`, `newsreader-var.woff2`,
  `newsreader-var-italic.woff2`, `archivo-2ax.woff2` + `fonts.css` 항목
- 잔재: `pretendard-var-subset.woff2` (첫 서브셋 시도의 미사용 산출물)

남은 디스플레이 서체는 **Gabarito(CALM)** 하나. 한글 Pretendard 조각은
그대로 — CALM의 글자를 이미 전부 포함하므로 재생성 불필요
(원한다면 `python scripts/subset_pretendard.py`로 kr-core를 조금 줄일 수는 있음).

## 왜 시안 전환 구조를 안 지웠나

`registry.ts`·`VersionPicker`·`useVersion`·`App`의 lazy 라우팅을
**일부러 남겼다.** 후보가 하나뿐이면 없어도 되지만:

- CALM이 "확정 UI"가 아니라 "후보"임을 구조로 드러낸다. 우상단
  `시안 정보` 버튼(키 `v`)을 열면 "로봇 확정 전 검토 중인 후보입니다"와
  함께 후보 목록이 뜬다.
- 나중에 후보를 다시 늘리거나 교체할 때 그대로 쓴다. 시안을 `versions/`에
  추가하고 `VERSIONS` 배열에 한 줄 넣으면 끝.

`VERSIONS`는 이제 `[calm]`, `DEFAULT_VERSION = 'calm'`, `VersionId = 'calm'`.
삭제된 시안 주소(`?ui=instrument` 등)는 `isVersionId`가 걸러 CALM으로
폴백한다.

## 검증

`npm run build` 통과(청크가 시안별 5벌 → CALM 1벌로 줄어듦). Playwright로:

- CALM이 Gabarito를 실제 로드, 가로 스크롤 없음, tabular-nums 적용
- `?ui=instrument`/`?ui=stadium`이 CALM으로 폴백, 삭제 시안 루트
  (`.ins`/`.alm`/`.std`) 잔재 없음
- 피커 후보 1개, 콘솔 에러 없음

## 관련

- [`web/DESIGN.md`](../../web/DESIGN.md) §2에 남은 후보 CALM + 삭제 시안
  3종(참고)·백업 경로 정리
- 되돌리기: `backup/web_2026-07-20_pre_redesign/src/versions/` 에서 폴더와
  `fonts.css`·폰트 파일을 가져오면 됨
