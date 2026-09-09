# 제3자 자산 표기

이 리포가 재배포하는 **남의 저작물** 목록이다. 각 라이선스가 요구하는 표기를 여기에
모아둔다. 코드(`src/`, `web/app/`, `3d_model/source/`)와 측정값은 자체 저작물이다.

리포 자체의 라이선스는 아직 정하지 않았다 — [README §10](README.md#10-모델--제3자-자산).

---

## 1. 서체 — SIL Open Font License 1.1

**OFL은 폰트를 재배포할 때 라이선스 사본을 함께 배포할 것을 요구한다.** 사본은
[`web/public/fonts/licenses/`](web/public/fonts/licenses/)에 있다.

### Pretendard

- Copyright (c) 2021, Kil Hyung-jin (<https://github.com/orioncactus/pretendard>),
  with Reserved Font Name "Pretendard"
- 라이선스: SIL OFL 1.1 — [`OFL-Pretendard.txt`](web/public/fonts/licenses/OFL-Pretendard.txt)
- Pretendard는 아래 서체들에서 파생됐고, 그 표기도 위 라이선스 파일에 함께 들어 있다:
  - Copyright 2014-2021 Adobe (<http://www.adobe.com/>), with Reserved Font Name "Source"
  - Copyright (c) 2016 The Inter Project Authors (<https://github.com/rsms/inter>),
    with Reserved Font Name "Inter"
  - Copyright 2021 The M+ FONTS Project Authors
    (<https://github.com/coz-m/MPLUS_FONTS>), with Reserved Font Name "M PLUS 1"

> **원본을 그대로 싣지 않았다.** `web/scripts/subset_pretendard.py`로 unicode-range
> 서브셋을 만들어 `web/public/fonts/pretendard/*.woff2`로 쪼갰다(원본 2.0 MB → 조각).
> OFL은 수정·재배포를 허용하며, 예약 폰트명("Pretendard")을 그대로 쓰므로 서브셋임을
> 여기 명시한다.

### Gabarito

- Copyright 2023 The Gabarito Project Authors (<https://github.com/naipefoundry/gabarito>)
- 라이선스: SIL OFL 1.1 — [`OFL-Gabarito.txt`](web/public/fonts/licenses/OFL-Gabarito.txt)
- `web/public/fonts/gabarito-var.woff2` (변형 없음)

> 두 서체 모두 **React 시안(`web/src/`) 전용**이다. 실제 배포 UI인
> `web/app/index.html`은 시스템 폰트만 쓴다([`docs/05`](docs/05_web_ui_fluid.md) §10).

---

## 2. 추론 모델 — MoveNet Thunder INT8

- `models/movenet_thunder_int8.tflite` (7.1 MB)
- 출처: TensorFlow Hub (Google) —
  `https://tfhub.dev/google/lite-model/movenet/singlepose/thunder/tflite/int8/4`
- 모델 코드: **Apache License 2.0** (Google)
- 학습 데이터 기반 산출물: **CC BY 4.0** — 저작자 표시가 요구된다

필요 표기:

> MoveNet SinglePose Thunder (INT8), © Google. Licensed under Apache-2.0;
> model card and derived assets under CC BY 4.0.

변형하지 않았다 — 받은 파일 그대로 추론에만 쓴다.

---

## 3. 서보 — ST3215 / Feetech 프로토콜

`src/st3215_bus.py`는 Feetech SCS/STS 프로토콜을 **pyserial로 자체 구현**한 것이다.
벤더 SDK를 가져오지 않았다. 레지스터 주소·부호비트 해석은 공개된 오픈소스
[LeRobot](https://github.com/huggingface/lerobot)(Apache-2.0)의
`motors/feetech/`로 교차검증했다 —
[`docs/issues/2026-07-17_01`](docs/issues/2026-07-17_01_homing_offset_wrong_sign_bit_caused_physical_snap.md).

> 벤더 배포 CAD(`ST3215.step`)는 **재배포하지 않는다.** 2026-08-08에 리포에서 제거했고
> `.gitignore`가 `*.step`을 막는다. 필요하면 제조사 페이지에서 직접 받을 것.

---

## 4. 런타임 의존성

컨테이너가 PyPI에서 받아 설치하는 것들이고, 이 리포가 재배포하지 않는다.
전체 목록은 [`docker/requirements.txt`](docker/requirements.txt).

| 패키지 | 라이선스 |
|---|---|
| `ai-edge-litert` | Apache-2.0 |
| `opencv-python-headless` | Apache-2.0 |
| `numpy` | BSD-3-Clause |
| `pyserial` | BSD-3-Clause |

---

## 5. 이 리포에 **없는** 것

혼동을 막기 위해 적어둔다.

| | 왜 없나 |
|---|---|
| YOLO 계열 가중치 | 이 라인은 MoveNet만 쓴다. Ultralytics(AGPL-3.0) 자산은 애초에 들어온 적이 없다 |
| Qualcomm AI Hub 산출물 | Qualcomm EULA(proprietary)라 재배포하지 않는다 |
| 벤더 CAD (`*.step`) | §3 참고 |
| 경비 모드 촬영본 (`captures/`) | 사람이 찍히므로 `.gitignore` |
