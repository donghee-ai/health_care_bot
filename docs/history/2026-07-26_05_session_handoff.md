# 2026-07-26 세션 핸드오프 — 애플 UI 통일 · 운동 종목 개편 · 상체/하체 추적

> 다음 세션은 이 문서부터 읽으면 오늘까지의 맥락이 잡힙니다. 하드웨어/서보/PTZ
> 저수준 배경은 `docs/HANDOFF.md`(07-17), 종목 감지 설계는
> `docs/exercise_detection.md` 참고.
>
> **경로 안내 (2026-07-30 재편)** — 위 두 문서는 `docs/00~09` 번호 체계로 이관됐습니다:
> HANDOFF → [`06_hardware_calibration.md`](../06_hardware_calibration.md)(하드웨어 값) ·
> [`07_runbook.md`](../07_runbook.md)(실행/환경) · [`08_troubleshooting.md`](../08_troubleshooting.md)(함정),
> exercise_detection → [`04_algorithm_exercise.md`](../04_algorithm_exercise.md).
> 전체 지도는 [`00_project_blueprint.md`](../00_project_blueprint.md) §6.

---

## 1. 한 줄 요약

애플 디자인 라이브 UI를 만들어 **:8080/app 하나로 통일**했고, 운동 종목을
**스쿼트 + 숄더프레스 + 레터럴레이즈**(푸시업 삭제)로 개편, **PTZ 추적을 종목별
상체/하체로 분리**했다. 웹 UI에서 종목 선택 + 누구나 조종(공유 제어권).

---

## 2. 지금 돌고 있는 것 (현재 상태)

- 디바이스(`arduino@192.168.0.45`)에서 **run.sh 서비스 실행 중** (screen 세션 `hcb`).
- **`http://192.168.0.45:8080/app` = 애플 "Fluid" 디자인** (라이브 로봇 카메라 + 실제 데이터).
- 카메라 = `/dev/video2` (run.sh가 USB 카메라 자동탐색), 서보 = `/dev/ttyACM0`, fps ~11.
- 운동 종목 = **squat / overhead / lateral**, 웹 UI에서 선택.
- 제어 = 공유 제어권 `client_id="hcb-demo"` + PIN `1234` → 접속한 누구나 조종.

**실행/중지:**
```bash
ssh arduino@192.168.0.45
cd ~/health_care_bot && bash docker/run.sh      # 카메라 자동(video2), /app=애플
docker stop health-care-bot                      # 중지
```
접속: `http://192.168.0.45:8080/app` (운영자 PTZ: 설정 없이 바로 조종됨 / 뷰어와 동일 화면)

---

## 3. 오늘 한 일 (주제별)

1. **애플 디자인 스킬 설치** — Emil Kowalski `npx skills@latest add emilkowalski/skills`
   (apple-design 외 5종, 전역 `~/.claude/skills`). `review-animations`는 사용자 직접 호출 전용.
2. **라이브 시안 2종 신규** (`design_demos/`):
   - `live_frontend-design.html` "Field Optics" (광학 계기)
   - `live_apple-design.html` "Fluid" (스프링 물리) — **이게 메인**
3. **로봇 실카메라 연동** — `/stream.mjpg` + `/stats.json` 폴링, 레티클=실제 추적 좌표,
   없으면 getUserMedia 데모 폴백.
4. **공유 제어권** — 모든 클라이언트가 `hcb-demo` 공유 → 잠금 없이 누구나 조종(마지막 명령 우선).
   조이스틱=실서보, 모드/auto_track=실제 API.
5. **Fluid 개선** — PTZ 자동추적↔직접조작 토글(자동=텔레메트리 FPS/추론/CPU온도/RAM,
   수동=조이스틱), 설정 기어+QR 모바일 접속, **컴퓨터/모바일 분리 레이아웃**
   (PC=큰 카메라+정보 아래, 폰=한 화면).
6. **8080 통일** — `web/dist/index.html`=애플 페이지(자체포함 HTML), stock은
   `index.html.stock.bak` 백업. `run.sh`에 카메라 자동탐색(video2) 굽음.
7. **모바일 접속 디버그** — 폰 접속 실패 → **폰 랜덤 MAC** 원인 규명·해결
   (`issues/2026-07-26_01`).
8. **운동 종목 개편** — 푸시업 삭제, 숄더프레스·레터럴 추가, 자동분류 제거→웹 명시 선택
   (`history/2026-07-26_02`).
9. **PTZ 상체/하체 추적 분리** — 스쿼트=무릎, 상체운동=어깨(머리 위 팔 안 잘리게)
   (`history/2026-07-26_03`).
10. **문서화** — `docs/exercise_detection.md` 설계문서 (`history/2026-07-26_04`).

---

## 4. 코드 변경 (건드린 파일)

**백엔드 (`src/`):**
- `exercise_counter.py` — PushupCounter 자리에 OverheadPressCounter(60/140)·LateralRaiseCounter(35/80).
- `angles.py` — `shoulder_elev_angle`(elbow-shoulder-hip) 추가.
- `main.py` — 종목 3개, `select_counter`(자동분류 제거), `compute_angle` 분기, stats 키
  squat/overhead/lateral, `ptz.set_track_mode(exercise)` 호출.
- `app_state.py` — mode 유효값 (squat/overhead/lateral), `session_finish(snaps)` 일반화.
- `http_server.py` — init_app/세션 API에 3 카운터.
- `ptz_controller.py` — `track_mode`(lower/upper), `set_track_mode`, `_target`(어깨/무릎),
  모드별 pitch 기준·데드존.
- `pose_utils.py` — `shoulder_center_normalized`.
- `docker/run.sh` — 카메라 USB 자동탐색(video2), `--mode auto`→`--mode squat`.

**프론트:** `web/dist/index.html`(=애플 Fluid, 소스 `design_demos/live_apple-design.html`) —
세그먼트 3버튼(스쿼트/숄더프레스/레터럴), 활성 모드 카운터 표시.

---

## 5. 디자인 자산 현황 (총 8종)

- **React 앱 시안 6종** (`web/src/versions/`, `registry.ts`): CALM(기본)·PULSE·AURORA·
  CORE·CARE(rehab)·LIVE(session). **단, 빌드 산출물이 Fluid로 덮여 지금 서빙 안 됨**
  (보려면 빌드 or 예전 컴파일본 서빙). `web/DESIGN.md`는 07-21 기준이라 "CALM 1종"으로
  오래됨 — registry가 최신(6종).
- **독립 HTML 2종** (`design_demos/`): Field Optics, Fluid(=현재 /app).
- 목업 보드: `docs/design_refs_2026-07-25/candidate-board.html` (정적, 빌드없이 열림).
- 백업: `web/dist/index.html.stock.bak`(stock React), `backup/web_2026-07-20_pre_redesign/`.

---

## 6. 다음 할 일 (실측 필요, 우선순위)

1. **운동 3종 실제 사람으로 카운팅 검증·임계 튜닝** — 임계값은 합리적 기본값일 뿐.
   누락/중복 시 조정. (레터럴은 팔꿈치 곧게, 정면 응시 필요)
2. **PTZ 상체 프레이밍 실측** — 숄더프레스/레터럴 시 머리 위 팔이 프레임에 남는지.
   잘리면 `ptz_controller.py::pitch_target_y_upper`를 0.64→0.68~0.72로.
3. **스쿼트 회귀 확인** — 종전과 동일하게 추적/카운트되는지.
4. (선택) React 6종 정리 or 애플 Fluid로 완전 확정.

---

## 7. 오늘 새로 안 함정 (재발 방지)

- **run.sh 하드코딩 인자 ↔ argparse 동기화**: argparse `--mode`에서 `auto` 뺐더니
  run.sh의 `--mode auto`가 컨테이너를 즉시 죽였다. `--rm`이라 `docker logs`엔 안 남음
  → `run.sh > /tmp/hcb_run.log 2>&1`로 캡처해서 진단. argparse choices 바꿀 땐 run.sh도 확인.
- **폰 랜덤 MAC** = `ERR_ADDRESS_UNREACHABLE` (그 네트워크에서 랜덤MAC 끄면 해결).
  상세 `issues/2026-07-26_01`.
- **애플 페이지는 정적 HTML** → `npm run build` 하면 `web/dist/index.html`이 stock으로
  덮인다. 애플 유지하려면 재배포(백업 `index.html.stock.bak`).
- **카메라 노드는 부팅마다 바뀜** — run.sh가 자동탐색하지만, 안되면
  `for v in /sys/class/video4linux/video*; do echo "$(basename $v) $(cat $v/name)"; done`.
- SSH stdin 파일전송 시 `pkill -f "http.server 8777"`는 **자기 셸까지 매칭**해 세션이
  끊긴다(exit 255) — PID로 kill 하거나 bracket 트릭.

---

## 8. 관련 문서 / 히스토리 (오늘)

- 설계: [`04_algorithm_exercise.md`](../04_algorithm_exercise.md) (당시 `exercise_detection.md`)
- [`2026-07-26_01`](2026-07-26_01_apple_design_ui_live_and_8080_unify.md) 애플 UI + 8080 통일
- [`2026-07-26_02`](2026-07-26_02_pushup_removed_overhead_lateral_added.md) 종목 개편
- [`2026-07-26_03`](2026-07-26_03_ptz_track_mode_upper_lower_body.md) PTZ 상체/하체
- [`2026-07-26_04`](2026-07-26_04_exercise_detection_doc.md) 설계 문서화
- 이슈: [`issues/2026-07-26_01`](../issues/2026-07-26_01_mobile_web_access_fails_random_mac.md) 폰 랜덤 MAC
