# 2026-07-26 — 푸시업 제거 + 숄더프레스·레터럴레이즈 추가 (정면 선택식)

## 시점

2026-07-26. [`2026-07-26_01`](2026-07-26_01_apple_design_ui_live_and_8080_unify.md)에서 애플 UI를
:8080/app으로 통일한 뒤. 사용자가 "푸시업은 정면/사선에서 애매하다"고 지적 → 종목 개편.

## 왜

**푸시업은 2D 포즈에 부적합.** 팔이 카메라 앞뒤(depth 방향)로 굽고, 몸 방향
자동분류(세로=squat/가로=pushup)가 사선·정면 자세를 오분류한다. → 푸시업을
빼고, **정면을 보고 서서 이미지 평면 안에서 움직이는** 상체 종목으로 교체.

## 무엇을

- **삭제**: 푸시업 (파이프라인·UI·mode에서). 자동 몸방향 분류(select_counter의
  orientation 분기)도 제거 — 전부 정면 종목이라 **모드는 웹 UI에서 명시 선택**.
- **추가**: 숄더프레스(overhead) + 사이드 레터럴 레이즈(lateral).
- 두 종목 모두 **어깨 올림 각도 하나**로 카운트: `shoulder_elev_angle` =
  elbow-shoulder-hip. 팔 내림≈10~20°, 옆 수평(레터럴)≈90°, 머리 위(프레스)≈160~170°.

## 구현 (파일별)

- `src/angles.py`: `shoulder_elev_angle(kp, side)` 추가 (elbow-shoulder-hip). `elbow_angle`는
  미사용으로 남김(무해).
- `src/exercise_counter.py`: `PushupCounter` 자리에 `OverheadPressCounter`(down<60, up>140),
  `LateralRaiseCounter`(down<35, up>80) 추가. 기존 `RepCounter` 히스테리시스+dwell 그대로 재사용.
  (RepCounter 상태 의미: 팔 내림=DOWN, 팔 올림=UP → 올릴 때 rep 카운트.)
- `src/main.py`: import 교체, `_HIGHLIGHT_ARM`(어깨·팔꿈치·손목), `select_counter(mode, squat_c,
  overhead_c, lateral_c)` — orientation 분기 제거하고 mode로만 선택, `compute_angle`에
  overhead/lateral 분기, 카운터 3개 생성, `--mode {squat,overhead,lateral}`(기본 squat),
  임계 플래그 `--overhead-*`/`--lateral-*`, stats에 `squat`/`overhead`/`lateral` 스냅샷.
- `src/app_state.py`: `set_mode` 유효값 `(squat,overhead,lateral)`, 세션 기본 mode `squat`,
  `session_finish(snaps, avg_fps)`로 일반화(reps/best_deg dict).
- `src/http_server.py`: `init_app`에 overhead_c/lateral_c, 세션 start/reset/finish에서 3개 리셋·스냅샷.
- `docker/run.sh`: `--mode auto` → `--mode squat` (아래 함정 참고).
- **프론트 `web/dist/index.html`(=애플 페이지)**: 세그먼트 3버튼(스쿼트/숄더프레스/레터럴),
  reps는 활성 모드 카운터(`d[mode].reps`)에서, 피드백 종목별 분기, 모드는 실제
  `app.session.mode` 반영. 소스: `design_demos/live_apple-design.html`.

## 함정 (재발 방지)

**argparse `choices`를 바꾸면 `docker/run.sh`의 하드코딩 인자도 같이 고쳐야 한다.**
`--mode`에서 `auto`를 없앴는데 run.sh가 `--mode auto`를 넘겨 컨테이너가 즉시 종료됐다
(`invalid choice: 'auto'`). `--rm`이라 `docker logs`엔 안 남아 `run.sh > /tmp/hcb_run.log 2>&1`로
캡처해서 원인 확인. → run.sh를 `--mode squat`로 수정.

## 검증

- 컨테이너 정상 기동(fps ~11, camera video2 자동).
- `stats.json` 카운터 키 = `squat`/`overhead`/`lateral` (pushup 없음).
- 제어권(hcb-demo/PIN 1234) 잡고 `/api/mode` 전환 실측:
  overhead(thr 60/140) · lateral(thr 35/80) · squat(thr 100/140) — `exercise_active`가 즉시 추종.
- `/app`에 3버튼 노출, pushup 없음. PC 접속 확인.

## 남은 것 (실제 측정 필요)

임계값은 **합리적 기본값**일 뿐 스쿼트처럼 실제 사람으로 튜닝 필요:
- overhead down<60/up>140, lateral down<35/up>80 — 실기에서 rep 누락/중복 확인 후 조정.
- 레터럴은 팔을 완전히 편 상태(팔꿈치 안 굽힘)가 각도가 깔끔. 굽히면 elbow가 hip 쪽으로 와 각도 왜곡 가능.
- 카운트가 정면 기준이라 사용자가 카메라를 정면으로 보고 서야 정확.

## 관련

- 실행: `cd ~/health_care_bot && bash docker/run.sh` → `http://192.168.0.45:8080/app`
- 이전: [`2026-07-26_01`](2026-07-26_01_apple_design_ui_live_and_8080_unify.md)
