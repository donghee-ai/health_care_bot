# 2026-07-20 — 웹앱 전면 재설계: 디자인 시안 4종 + 폰트 self-host

## 시점

2026-07-20 새벽. CPU 사용률 텔레메트리
([`2026-07-19_03`](2026-07-19_03_cpu_usage_telemetry.md)) 이후, 웹 UI만
따로 떼어 야간 작업으로 진행했다.

## 사건

기존 웹앱을 백업하고 **완전히 다른 성격의 디자인 시안 4개**를 새로 만들었다.
같은 데이터(스쿼트 카운트 · MoveNet 자세 · UNO Q 상태 모니터링)를 네 가지
방식으로 해석한 것으로, 하나를 고르기 위한 비교용이다.

**추론 루프는 건드리지 않았다.** `src/*.py`(MoveNet, 카운터, PTZ 제어),
`/stats.json`·`/api/*` 계약 모두 그대로다. 순수 프론트엔드 작업.

## 백업

```
health_care_bot/backup/web_2026-07-20_pre_redesign/
```

`src/`·`public/`·`dist/`·설정 파일 전부. 되돌리려면 이걸로 덮고 재빌드.

## 시안 4종

| | 성격 | 바탕 | 강조 | 디스플레이 서체 |
|---|---|---|---|---|
| INSTRUMENT | 정밀 계측기 | `#0a0b0d` | 라임 `#c8f751` | Spline Sans Mono |
| ALMANAC | 기록하는 종이 | `#f4f0e6` | 벽돌 `#8a3b2c` | Newsreader |
| STADIUM | 중계 스코어보드 | `#0b0b0b` | 주황 `#ff3b00` | Archivo (wght+wdth) |
| CALM | 숨쉬는 코치 | `#eef2ef` | 딥그린 `#0f4c3a` | Gabarito |

전환: `/app?ui=<id>`, 화면 내 버튼, 키보드 `1`~`4`.
상세 설계 근거는 [`web/DESIGN.md`](../../web/DESIGN.md).

## 리서치 방법

Playwright로 22개 사이트(WHOOP·Oura·Strava·Linear·Vercel·Eight Sleep·
Nike·Arc·Withings·Peloton 등)를 열어 **계산된 스타일을 직접 긁었다** —
스크린샷 눈대중이 아니라 실제 렌더된 `font-family`, 면적 가중 배경색,
텍스트 색, `border-radius`, `font-weight` 분포를 뽑았다.

여기서 나온 구체적 수치가 팔레트 결정의 근거가 됐다. 예: Linear는
`#08090a` 바탕에 2~6px radius, Oura는 `#f7f1e8` 크림 + 고대비 세리프,
Strava는 `#fc5200` 단일 강조색에 radius 4px.

## 뒤집힌 초기 판단

리서치가 처음 고른 서체 대부분을 무효화했다.

1. **Instrument Serif → Newsreader.** Instrument Serif는 Space Grotesk·
   Geist와 묶여 2026년 기준 "AI가 만든 화면"의 표식으로 지목되는 조합이다.
   Newsreader는 숫자가 기본 tabular + lining이라 표에 그대로 쓸 수 있다.
2. **Fraunces 탈락.** 바이너리를 뜯어보니 **`tnum` 기능이 아예 없다.**
   실시간으로 바뀌는 숫자를 다루는 앱에서 자릿수가 흔들리는 서체는
   후보가 될 수 없다.
3. **Anton → Archivo.** Anton은 단일 굵기. Archivo는 wght+wdth 2축이라
   압축 디스플레이(`wdth 78`)를 파일 하나로 내고 숫자 기능이 충실하다.
4. **Outfit → Gabarito**, **JetBrains Mono → Spline Sans Mono.**
   앞의 둘은 기본값 인상이 강해서 교체.

## 실제로 고친 결함

- **INSTRUMENT 팔레트 대비 미달.** `--ink-3`가 라벨 텍스트로 18곳에
  쓰이는데 읽기 한계 아래였다. 더 나쁜 건 **`--crit`(위험)이
  `--warn`(주의)보다 어두워서 가장 급한 상태가 가장 안 읽혔다는 점.**
  둘 다 밝은 쪽으로 올렸다.
- **`word-break: keep-all` 누락.** 한글 음절은 유니코드상 표의문자로
  분류돼서, 기본값이면 브라우저가 아무 음절 사이에서나 줄을 끊는다
  ("한국어를" → "한국 / 어를"). 한국어는 어절 사이를 띄우므로 이건
  틀린 동작이다. 전역 적용.
- **`font-feature-settings` 우선순위 함정.** 이게
  `font-variant-numeric`보다 우선해서, 어딘가에서 한 줄 선언되면
  tabular이 조용히 무력화된다. 숫자 요소에 방어적으로 `normal`을 건다.
- **커닝이 tabular을 깨는 경우.** 일부 서체는 고정폭 숫자에까지 커닝
  페어를 걸어둬 `"11111"`과 `"00000"` 폭이 달라진다. `font-kerning: none`.
- **`ch` 단위 함정.** Pretendard는 `1ch`가 tabular 자폭보다 약 3% 좁아서
  `width: 5ch`로 숫자 칸을 잡으면 조용히 잘린다. 안 썼다.

## 폰트 self-host — 2.0MB → 226KB

로봇은 LAN 전용이라 **구글 폰트 CDN에 못 나간다.** CDN을 쓰면 시연장에서
폰트만 통째로 안 뜨는 사고가 난다. 전부 self-host로 갔다.

문제는 Pretendard 원본이 2.0MB라는 것(한글 음절 11,172자 전부).
"QR 스캔 후 3초" 목표와 정면으로 부딪힌다.

`scripts/subset_pretendard.py`로 unicode-range 조각을 만든다.

**첫 시도(코드포인트 순 44조각)는 실패했다.** 한 화면에 쓰이는 글자가
조각 전체에 흩어져 있어서 텍스트 많은 시안이 **37조각을 요청**했다.
쪼갠 의미가 없었다.

**두 번째 시도가 통했다.** 소스에 실제로 등장하는 글자만 모은
`kr-core.woff2`(105KB)를 만들어 **맨 앞에 선언**하고, 나머지는 안전망으로
뒤에 뒀다. 안전망 조각은 문구를 바꿨을 때만 쓰이고, 모든 글자가 어딘가에는
있으므로 **두부(□)가 원천적으로 불가능하다.**

결과 (실측):

| 시안 | 폰트 전송량 | woff2 요청 수 |
|---|---|---|
| INSTRUMENT | 262 KB | 3 |
| ALMANAC | 346 KB | 4 |
| STADIUM | 314 KB | 3 |
| CALM | 260 KB | 3 |

Pretendard 원본 단독 2,009 KB → **공통 226 KB (base 121 + kr-core 105)**.
37요청 → 3~4요청.

원본은 `web/fonts-src/`에 둔다. `public/`에 두면 dist에 2MB가 그대로 실린다.

## 데모 모드

로봇 없이 시안을 검토·발표 리허설할 수 있게 `?demo=1`을 넣었다.
`/stats.json`에 한 번도 못 붙으면 자동으로 켜진다 — **실제 stats가
한 번이라도 도착하면 켜지지 않으므로 디바이스 동작에는 영향이 없다.**

합성 데이터는 실측 범위에 맞췄다(FPS 10.8, CPU 83%, 스쿼트 주기 3.2초).
카메라 자리에는 MoveNet과 같은 17 keypoint 골격을 무릎 각도에 맞춰 그린다.
데모일 때는 화면에 항상 표식이 뜬다(`DEMO`/`견본`/`둘러보기`).

## 구조

시안끼리 **스타일을 공유하지 않는다.** 각 시안이 자기 `.tsx` + `.css`를
통째로 소유하고 lazy로 나뉘어 있어, 보고 있는 시안의 CSS만 로딩된다.
네 벌의 CSS가 한꺼번에 들어와 서로 덮어쓰는 사고를 구조적으로 막았다.

공유하는 건 데이터와 동작뿐 — 훅은 값을 계산하고 상태를 관리할 뿐
마크업을 만들지 않는다(`useStats`, `useMjpeg`, `useRepPulse`,
`useSeries`, `usePressRepeat`, `useVersion`).

## 검증

`npm run build` 통과 + Playwright로 4시안 × 모바일(402px)/데스크톱(1440px):

- 각 시안이 자기 디스플레이 서체를 실제로 로드하는지 (폴백 아님) ✓
- Archivo `wdth: 78` 축이 실제로 적용되는지 ✓
- 큰 숫자에 tabular-nums가 걸려 있는지 ✓
- 가로 스크롤 없음 ✓
- 시안 전환 시트 열림 ✓
- 콘솔 에러 없음 ✓

## 남은 것

- **실기 미검증.** 데모 데이터와 빌드까지만 확인했다. UNO Q에 올려
  실제 MJPEG 스트림·실제 PTZ 조작으로 보는 건 아직 안 했다.
- 실제 스트림이 들어왔을 때의 프레임 밀도, 조작 지연, 발열 영향 확인 필요.
- 아이폰 사파리 실기 확인.
- 시안 4개 중 하나를 고르고 나머지를 정리하는 작업.
