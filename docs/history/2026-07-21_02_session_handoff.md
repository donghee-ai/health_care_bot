# 2026-07-21 — 세션 핸드오프 (웹 시안 · 디바이스 실행 · 성능 조사 · PTZ)

다음 세션에서 바로 이어받기 위한 상태 스냅샷 + 미결정 + 재현 명령.
이전 개요: [`2026-07-20_01`](2026-07-20_01_web_redesign_four_variants.md),
[`2026-07-21_01`](2026-07-21_01_web_variants_pruned_to_calm.md).

---

## 1. 지금 어떤 상태인가 (한눈에)

- **웹 시안 5종**이 시안 피커에 등록됨: `CALM · PULSE · AURORA · CARE(rehab) · LIVE(session)`.
  기본값 `calm`. 전환: 화면 `시안` 버튼 / 키 1–5 / URL `?ui=<id>`.
- **디바이스에서 앱이 실기로 실행 중** (UNO Q, `arduino@192.168.0.45`). 새 웹(dist) 배포 완료.
  카메라·서보 연결됨, HTTP 8080 서빙, 추론 ~11.4 FPS.
- **성능 조사 결론 확정**: 시스템은 **invoke(추론) 바운드**. 화면/인코딩 끄기·카메라레이트
  낮추기로는 FPS 안 오름(실측). 모델 안 바꾸면 유일한 큰 레버는 **NPU 델리게이트**.
- **PTZ 추적/관성 알고리즘**은 이번 세션에 코드 변경 없음. 설명·구조도만 산출.

---

## 2. 웹 — 디자인 시안 현황

경로: `web/src/versions/<id>/`, 등록: `web/src/versions/registry.ts`, 라우팅: `web/src/App.tsx`.

| id | 이름 | 성격 | 제작 |
|---|---|---|---|
| `calm` | CALM | 숨쉬는 코치 (Gentler Streak·Apple Fitness) · **기본값** | 이번 세션(초기 4종 중 유일 생존) |
| `pulse` | PULSE | 밝은 프로덕트 콘솔 (Toss·Dragonwing). 스쿼트+푸시업 2카드, STEP, +1 플로터 | 사용자 목업 기반 |
| `aurora` | AURORA | 유리 대시보드 (글래스모피즘). **플로팅 하단 바** + 3뷰(라이브/장치/제어) | 사용자 목업 기반 |
| `rehab` | CARE | 신뢰하는 재활 코치 | **사용자 제작** (내가 안 만든 파일) |
| `session` | LIVE | 세션 집중 스포츠 | **사용자 제작** |

- **삭제됨**(백업에 있음): INSTRUMENT·ALMANAC·STADIUM → `backup/web_2026-07-20_pre_redesign/src/versions/`.
- **원본 웹 백업**: `backup/web_2026-07-20_pre_redesign/` (되돌리려면 여기서 복원).
- 시안끼리 CSS/마크업 공유 안 함 (lazy 분리). 공유는 데이터+동작(훅)뿐.

### 공통 인프라
- **데모 모드** `?demo=1` — 로봇 없이 합성 데이터+가짜 골격. 실제 stats 오면 자동 해제.
- 훅: `useStats`(폴링+연결+데모폴백), `useMjpeg`, `useRepPulse`, `usePressRepeat`, `useVersion`.
  `useSeries`는 CALM 정리 때 삭제 → AURORA가 로컬 `useRolling`으로 자체 보유.
- **폰트 self-host**: Pretendard 2.0MB를 `web/scripts/subset_pretendard.py`로 unicode-range
  46조각화 (`web/public/fonts/pretendard/`). 원본은 `web/fonts-src/`(served 아님).
  한국어 문구 크게 바꾸면 재실행: `cd web && python scripts/subset_pretendard.py`.
- 설계 근거 문서: [`web/DESIGN.md`](../../web/DESIGN.md). (아직 CALM 위주라 PULSE/AURORA 미반영 — **갱신 필요**.)

### 미결정 (웹)
- **시안 확정** — 5종 중 무엇을 최종으로? (또는 계속 후보 병존)
- 푸시업 폐기 논의 → **취소됨**(원복). 현재 PULSE는 스쿼트+푸시업 둘 다 표시.
- `web/DESIGN.md`에 PULSE/AURORA/CARE/LIVE 반영 안 됨.

---

## 3. 디바이스 — 실행 상태 & 재현

**접속**: `ssh arduino@192.168.0.45` (키 인증, 비번 불필요). 호스트명 `unoq-korea01`.
**앱 위치**: `~/health_care_bot` (git 저장소 아님, 파일 복사 배포). **Docker로 실행**.
**런타임**: 컨테이너 `health-care-bot:22.04`. `~/.venvs/hcb`는 안 씀(의존성 없음).

### ⚠️ 지금 컨테이너가 **실행 중**입니다
- 카메라 ON, 서보 torque ON(움직임), HTTP 8080. 세션 종료 시 정리하려면:
  ```bash
  ssh arduino@192.168.0.45 'docker stop health-care-bot'
  ```

### 브라우저 접속 (같은 네트워크)
- `http://192.168.0.45:8080/app/?ui=aurora` (뷰어) · `...&role=operator` (조작, **PIN 1234**)
- 실기라 카메라 앞에 사람이 서야 추적·카운트 동작.

### 웹 재배포 (로컬 dist → 디바이스)
```bash
cd web && npm run build
tar -czf - dist | ssh arduino@192.168.0.45 \
  'cd ~/health_care_bot/web && rm -rf dist && tar -xzf -'
# http_server가 매 요청 디스크에서 읽으므로 컨테이너 재시작 불필요
```

### 앱 시작 (detached, run.sh는 -it라 비대화형 ssh 불가 → 직접 docker run)
```bash
ssh arduino@192.168.0.45 'cd ~/health_care_bot && \
  docker rm -f health-care-bot 2>/dev/null; \
  docker run -d --name health-care-bot --net host \
    --device /dev/video0 --device /dev/video1 --device /dev/ttyACM0 \
    -v "$PWD:/work" -w /work health-care-bot:22.04 \
    python3 /work/src/main.py /work/models/movenet_thunder_int8.tflite \
      --mode auto --camera 0 --serial /dev/ttyACM0 --serve 8080'
```

### 🔴 부팅마다 바뀌는 것 (매번 확인)
- **카메라 노드**: `/dev/videoN`이 부팅마다 바뀜. 이번엔 USB 카메라=video0/1, venus 코덱=video2/3
  → `--camera 0`. 다음 부팅엔 다를 수 있음. 확인:
  ```bash
  for f in /sys/class/video4linux/video*/name; do echo "$(basename $(dirname $f)): $(cat $f)"; done
  ```
  (`qcom-venus`가 아닌 노드가 진짜 카메라)
- **USB VBUS 이슈**: 카메라·서보(CH343 ttyACM0)는 UNO Q 직결 시 전원 안 가 인식 안 됨.
  **셀프파워 USB 허브** 필수. `lsusb`에 `ARC Camera`+`QinHeng CH343`+`Huasheng HUB` 떠야 정상.
- 서보 노드: 보통 `/dev/ttyACM0`.

---

## 4. 성능 조사 — 결론 (실측)

**질문**: 화면/스트리밍 끄면 FPS 오르나? 모델 교체 없이 추론 속도 올릴 수 있나?

### 실측 결과
| 실험 | 결과 |
|---|---|
| 인코딩 ON(serve 8080) vs OFF(serve 0) | FPS 11.34 ↔ 11.41 = **~0 차이** (오차) |
| 카메라 15fps 캡 시도 | 카메라가 무시(actual=30.5 유지) → 비교 불가 |
| CPU 4코어 | 전부 **2016MHz = 최대** (schedutil 이미 최대까지 밀어붙임) |
| CPU 명령셋 | `asimd`만, **`asimddp`(INT8 dotprod) 없음** → INT8 고속 커널 못 씀 |
| 온도(추론 중) | 65~73°C (throttle 전) |

### 왜 안 오르나
- 루프 직렬(`grab→invoke→draw→encode`), **invoke가 지배**. invoke 구간 4코어 100%,
  그리기/인코딩 구간 1코어(3코어 놀음) → 평균 CPU ~85%.
- 화면 끄면 없어지는 건 "3코어 노는 구간"의 작은 꼬리라 invoke가 쓸 코어를 못 늘림 → ~0.
- 병목 = **invoke 지연 그 자체**. 남는 15%는 invoke가 못 쓰는 단일스레드 유휴.

### 모델 교체 없이 올리는 법 (효과 순)
1. **NPU/DSP 델리게이트 (Qualcomm Hexagon HTP · QNN/LiteRT)** — 유일한 큰 레버.
   CPU가 dotprod 없어 INT8에 불리 → INT8 전용 하드웨어로 오프로드하면 크게 빨라지고 CPU도 풀림.
   **다음 세션 착수 지점**: 델리게이트 가능 여부 확인 (`libQnn*`/Hexagon 라이브러리, `ai_edge_litert`
   델리게이트 API, AI Hub QNN 컴파일 모델 필요 여부).
2. Adreno GPU 델리게이트 — INT8엔 애매(FP16 선호).
3. 클럭/거버너 — 이미 최대, 효과 없음.
4. 발열 관리 — soak에서 클럭 유지용(부스트 아님).
5. 스레드/파이프라인(draw·encode를 다음 invoke와 겹침) — 소폭 ~10%, 복잡도↑.

> 모델 교체(Thunder→Lightning)는 사용자 지시로 **제외**.

### 관련 산출물
- 승인된 계획 파일 `C:\Users\A\.claude\plans\composed-churning-truffle.md`
  (스트리밍 온/오프 게이팅) — **측정 결과 실익 ~0으로 사실상 폐기 권고.**

---

## 5. PTZ 추적 / 관성(coast) — 이번 세션엔 코드 변경 없음

- 코드: `src/ptz_controller.py`(`update` 326행, `_recover_yaw` 275행), `src/pose_utils.py`(`_target`),
  `src/st3215_bus.py`(서보). 알고리즘 문서: [`2026-07-19_02`](2026-07-19_02_ptz_time_based_control_and_loss_recovery.md).
- **구조도 아티팩트**(mermaid): https://claude.ai/code/artifact/88ddcc5f-215f-4031-b3f3-1a8470d2c277
- 논의된 개선안 (미착수):
  - 관성 "등속" 전환 검토 → **기각 권고**(overshoot↑·FPS의존↑·급정거). 감쇠 유지가 맞음.
  - 일관성 원하면: `coast_frames`→시간 기준, `coast_fov_deg` 실측 보정, 관성 거리 하드캡. 감쇠는 유지.
- 코드 vs 문서 불일치(참고): `2026-07-19_02` 요약 블록의 "10프레임/0.8"은 stale, **실제 15/0.9**.

---

## 6. 다음 세션 착수 후보 (우선순위 제안)

1. **NPU 델리게이트 가능성 조사** — 정확도 안 버리고 FPS 올리는 정공법. §4 착수 지점 참고.
2. **웹 시안 확정** — 5종 중 선택 → 나머지 정리 + `web/DESIGN.md` 갱신.
3. 실기 UX 다듬기 — 카메라 앞에서 각 시안 실제 동작 확인(추적·카운트·PTZ 조작·PIN).
4. (선택) PTZ 일관성 튜닝 — coast 시간 기준화 + fov 보정.

---

## 6-1. 세션 막판 코드 변경 — 영상 오버레이 텍스트 제거 (미검증)

- `src/main.py` 그리기 블록에서 **FPS/각도/REPS/PTZ 글자 오버레이(`putText`) 전부 제거**.
  스켈레톤(`draw_pose`)은 유지. 이유: 그 수치는 웹 UI가 stats.json으로 이미 표시 → 중복.
- FPS 계산·`ptz_snap`은 stats.json/로그에 쓰이므로 남겨둠. 로컬 `py_compile` 통과.
- **로컬 + 디바이스(`~/health_care_bot/src/main.py`) 둘 다 반영 완료.** 컨테이너는 정지 상태라
  **다음 `docker run` 때 적용**된다.
- ⚠️ **실기 미검증** — 다음 세션에 앱 띄워 영상에 글자 없이 골격만 나오는지 + FPS 변화(putText
  제거分, 아마 소폭) 확인 필요.

## 6-2. 연산 집중 모드 — `--idle-skip-draw` (opt-in, 기본 OFF)

- `main.py`에 플래그 추가 + `http_server.py`에 하위호환 변경(`update_live_state(..., encode=)`,
  `viewer_count()`). **플래그 없으면 기존과 100% 동일**(항상 그리기+인코딩).
- `--idle-skip-draw` 주면: **스트림 뷰어 0명일 때 그리기+인코딩을 통째로 skip**(stats.json 숫자는 계속).
  무영상 시안 CORE(= `/stream.mjpg` 안 엶)로만 보면 로봇이 인코딩 없이 추론에 집중.
  영상 시안(CALM/PULSE/…)을 열면 viewer_count>0 → 정상적으로 그리고 인코딩.
- 실행:
  - 기존(비게이팅): `... --serve 8080`
  - 게이팅: `... --serve 8080 --idle-skip-draw`
- ✅ **실기 검증됨(2026-07-21)** — 게이팅(뷰어0·인코딩skip) FPS **~11.44 (11.2~11.6, 안정적)**
  vs 비게이팅 ~11.34. **이득 ~0.1~0.3 fps + 변동 감소(안정화)** — 예측한 "소폭"과 일치.
  천장 ~11.4는 invoke(추론) 바운드 그대로. 정확도 손해 0, 기본 동작 보존.
- 새 웹 시안 **CORE** 추가(무영상, 스쿼트+장치 수치). 시안 총 6종.

## 7. 주의사항 요약
- 디바이스 컨테이너 **현재 실행 중** — 안 쓰면 `docker stop health-care-bot`.
- 카메라 노드·USB 인식은 **부팅마다 확인**(§3).
- 운영자 PIN `1234` (`src/app_state.py`).
- 로컬 미리보기: `cd web && npm run preview -- --host` → `http://localhost:4173/app/?demo=1&ui=aurora`.
- 커밋은 이번 세션에 안 함. (프로젝트 관례: 커밋 전 히스토리 먼저.)
