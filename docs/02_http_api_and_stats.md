# HTTP API 계약 · `stats.json` 스키마

본 문서는 로봇이 노출하는 HTTP 인터페이스 전체와 `stats.json`의 모든 필드를 정의합니다.
프론트엔드(또는 외부 도구)를 만들 때의 계약 문서이며, 필드를 읽을 때의 함정도 함께
적습니다.

구현: [`src/http_server.py`](../src/http_server.py) · [`src/app_state.py`](../src/app_state.py)
소비자: [`05_web_ui_fluid.md`](05_web_ui_fluid.md)

## 0. 한 눈에

```
GET  /                → 디버그 index (스트림 + stats 원본)
GET  /stream.mjpg     → multipart MJPEG 라이브 스트림
GET  /stats.json      → 전체 상태 (§3)
GET  /app, /app/*     → web/dist 정적 서빙 (SPA 폴백)

POST /api/control/claim | heartbeat | release     제어권
POST /api/ptz                                     카메라 조작
POST /api/mode                                    운동 종목
POST /api/session/start | pause | resume | reset | finish
```

- 서버: `http.server` + `ThreadingMixIn`, `0.0.0.0:8080`, 백그라운드 스레드.
- `GET`은 전부 **무인증**. `POST`는 전부 **제어권 lock 필요**(claim/heartbeat/release 제외).
- 응답에 `Access-Control-Allow-Origin: *`이 붙어 다른 오리진에서도 붙을 수 있다.

## 1. 엔드포인트

| Method | 경로 | 본문 | 보호 |
|---|---|---|---|
| GET | `/` | — | 없음 |
| GET | `/stream.mjpg` | — | 없음 |
| GET | `/stats.json` | — | 없음 |
| GET | `/app`, `/app/*` | — | 없음 |
| POST | `/api/control/claim` | `{client_id, pin}` | PIN |
| POST | `/api/control/heartbeat` | `{client_id}` | 보유자만 |
| POST | `/api/control/release` | `{client_id}` | 보유자만 |
| POST | `/api/ptz` | `{client_id, command, delta_deg?, enabled?}` | 제어권 |
| POST | `/api/mode` | `{client_id, mode}` | 제어권 |
| POST | `/api/session/start` | `{client_id, target_reps?}` | 제어권 |
| POST | `/api/session/pause`\|`resume`\|`reset`\|`finish` | `{client_id}` | 제어권 |

**모든 POST body에 `client_id`가 필요하다.** 없거나 lock 보유자가 아니면
`403 {"ok": false, "error": "control_not_claimed"}`.

### 1-1. `/api/ptz` 명령

| `command` | 추가 필드 | 동작 |
|---|---|---|
| `pan` | `delta_deg` | yaw 상대 이동. **±10°로 클램프**. `auto_track`을 끈다 |
| `tilt` | `delta_deg` | pitch 상대 이동. 동일 |
| `center` | — | 중앙(180/180) 복귀. **auto 상태는 건드리지 않음** |
| `auto_track` | `enabled` | 자동 추적 on/off |
| `stop` | — | 자동 추적 off (정지) |

수동 조작이 자동 추적을 끄는 이유: 조작하는 동안 카메라가 계속 되돌아가면 조작 자체가
불가능해진다. 응답은 `{"ok": true, "ptz": <snapshot>}`.

### 1-2. `/api/mode`

`{"mode": "squat" | "overhead" | "lateral" | "guard"}`. 그 외 값은
`{"ok": false, "error": "invalid_mode"}`.

**즉시 반영된다** — 추론 루프가 매 프레임 `app_state.get_mode()`를 읽기 때문이다.
카운터 3개는 항상 살아 있어 모드를 바꿔도 각자 횟수를 유지한다.

**`guard`(경비 모드)는 운동이 아니다** — rep 카운터가 없고, 전환 시점부터
`GUARD_ARM_DELAY_MS`(기본 5,000ms) 뒤에 "무장"된다. 무장 후 사람이 감지되면
원본 프레임을 `captures/guard_<타임스탬프>.jpg`로 저장하고
`captures/guard_log.jsonl`에 한 줄(`time`, `ts_ms`, `file`) 추가한다.
연속 촬영은 `GUARD_CAPTURE_COOLDOWN_MS`(기본 5,000ms)로 제한한다. `guard` 이외
모드로 전환하면 즉시 비무장 상태로 리셋된다. 구현: `src/guard_capture.py` +
`app_state.py`의 `guard_*` 함수. `captures/`는 `.gitignore` 대상(사람 사진 +
로그이므로 리포에 커밋하지 않는다).

### 1-3. 세션 전이

```
idle ──start──> running ──pause──> paused ──resume──> running ──finish──> finished
  ^                                                                          │
  └──────────────────────── reset ───────────────────────────────────────────┘
```

- `start`·`reset`은 **카운터 3개를 모두 리셋**한다.
- `pause`는 `running`이 아니면 `not_running`, `resume`은 `paused`가 아니면 `not_paused`.
- `finish`는 활성 세션이 없으면 `no_active_session`. 성공 시 요약을 반환하고
  `session.last_finished`에 저장한다(결과 화면용).
- 경과 시간은 일시정지 구간을 빼고 계산한다(`paused_elapsed_ms`).

## 2. 제어권 모델

```python
_operator_pin = "1234"        # src/app_state.py — 평문 하드코딩
_CONTROL_LOCK_MS = 60_000     # claim 후 60초
```

- `claim(client_id, pin)` — PIN이 맞고, **다른 client가 유효한 lock을 쥐고 있지 않으면**
  획득. 아니면 `locked_by_other`.
- `heartbeat(client_id)` — 보유자면 60초 연장. 아니면 `not_holder`.
- `release(client_id)` — 보유자면 해제.
- lock은 프로세스 메모리에만 있어 **재시작 시 사라진다**(좀비 lock이 안 남는 게 안전).

> **현재 데모 페이지는 모든 클라이언트가 `client_id="hcb-demo"`를 공유**하도록 만들어져
> 있다. 즉 PIN 입력 없이 **접속한 누구나 조종**하고 마지막 명령이 이긴다. 의도된 시연
> 편의이며, 격리가 필요하면 기기별 랜덤 `client_id` + PIN UI로 바꿔야 한다.
> 상세: [`05_web_ui_fluid.md`](05_web_ui_fluid.md) §5

## 3. `stats.json` 스키마

추론 루프가 매 프레임 채우고, 핸들러가 앱 상태를 덧붙여 응답한다.

```jsonc
{
  "frame": 1234,                  // 누적 프레임
  "fps": 11.3,                    // 최근 30 루프 평균 기준
  "loop_ms": 88.4,
  "mode": "squat",                 // 선택된 종목 (app_state)
  "exercise_active": "squat",       // 실제로 돌고 있는 카운터
  "orientation": "vertical",        // 표시용 (분류에는 미사용)
  "angle_deg": { "left": 168.2, "right": 171.0, "used": 169.6 },
  "person_center_norm": [0.51, 0.62],   // (x, y) 정규화 — 추적점과 별개
  "squat":    { "name": "squat", "state": "UP", "reps": 7,
                "deepest_overall_deg": 88.1, "last_rep_min_deg": 92.4,
                "current_down_min_deg": null,
                "thresholds_deg": { "down": 100.0, "up": 140.0 } },
  "overhead": { ... }, "lateral": { ... },   // 같은 형태, 항상 셋 다 존재
  "ptz": {
    "enabled": true, "state": "in_frame|edge|lost", "locked": false,
    "miss_frames": 0, "target_norm": [0.49, 0.61],
    "pan_cmds_total": 812, "tilt_cmds_total": 64,
    "sector_side": 0.1667, "grace_frames": 15, "auto_track_enabled": true,
    "pan_deg": 183.4, "tilt_deg": 178.9,
    "pan_offset_deg": 3.4, "tilt_offset_deg": -1.1
  },
  "last_ptz_cmd": "YAW 183.4",
  "last_event": { "exercise": "squat", "type": "REP", "rep_total": 7,
                  "min_angle_deg": 92.4, "frame": 1230 },   // rep 순간에만
  "dropped_frames": 0,
  "rss_mb": 214.6,
  "cpu_temp_c": 63.1,             // /sys/class/thermal/thermal_zone0/temp, 없으면 null
  "cpu_percent": 83.2,            // /proc/stat 차분 — 첫 호출은 항상 null
  "frame_ts_ms": 1753849123456.7,
  "app": {
    "session": { "session_id": "20260726-183000-a1b2", "mode": "squat",
                 "status": "idle|running|paused|finished", "target_reps": 20,
                 "started_at_ms": null, "paused_elapsed_ms": 0.0,
                 "pause_started_ms": null, "last_finished": null,
                 "elapsed_ms": 0 },
    "control": { "locked": true, "locked_by": "hcb-demo", "lock_remaining_ms": 42000 },
    "guard": { "active": false, "armed": false, "arm_remaining_ms": 0,
               "capture_count": 0, "last_capture_ms": null },
    "viewer_count": 1
  }
}
```

`app.guard`는 `mode`와 무관하게 항상 존재한다(`active`가 현재 guard 모드인지를
가리킨다). `guard` 모드에서 촬영이 발생한 프레임의 `last_event`는
`{"exercise": "guard", "type": "GUARD_CAPTURE", "file": "...", "time": "...", "frame": N}`
형태다(§1-2 참고).

### 3-1. 세션 요약 (`session/finish` 응답 · `last_finished`)

```jsonc
{
  "session_id": "...", "mode": "squat", "elapsed_ms": 184000,
  "reps":     { "squat": 12, "overhead": 0, "lateral": 0 },
  "best_deg": { "squat": 88.1, "overhead": null, "lateral": null },
  "avg_fps": 11.3, "finished_at_ms": 1753849123456
}
```

## 4. 필드를 읽을 때의 함정

- **`cpu_percent`의 첫 응답은 항상 `null`이다** — `/proc/stat`은 부팅 이후 누적값이라
  직전 샘플과의 차분이 필요하다. 프론트는 이때 `—`를 표시해야 한다.
- **`cpu_percent`는 디바이스 전체 부하다.** 컨테이너 안에서도 `/proc/stat`은 호스트
  전체를 보여준다(procfs는 네임스페이스 분리 안 됨). 이 프로세스만의 사용률이 아니다.
- **`ptz.pan_deg`는 우리가 명령한 목표각이다.** 서보의 실제 위치를 읽어오지 않는다.
  중앙 기준 상대각이 필요하면 `pan_offset_deg`를 쓴다.
- **`person_center_norm` ≠ `ptz.target_norm`.** 전자는 표시용 중심점(스쿼트는 무릎 가중
  평균), 후자가 실제 추적점이다. 레티클을 그릴 때 어느 쪽을 쓸지 의도적으로 골라야 한다.
- **PC/Windows에서 돌리면** `cpu_temp_c`·`rss_mb`·`cpu_percent`가 전부 `null`일 수 있다
  (`/proc`·`/sys` 없음). 정상 동작이다.
- **`squat`/`overhead`/`lateral` 세 블록은 항상 존재한다.** 활성 종목만 값이 변한다 —
  화면에 표시할 종목을 `mode`로 골라 `d[mode].reps`를 읽는 식이 안전하다.
- 스트림에 첫 JPEG가 오기 전에는 `/stream.mjpg`가 데이터를 안 보낸다. `--idle-skip-draw`로
  실행 중이고 뷰어가 0명이었다면 첫 프레임이 늦게 뜬다.

## 5. `/app` 정적 서빙

```
/app/<rel>  →  web/dist/<rel>       (없으면 web/dist/index.html 폴백 = SPA)
```

- `resolve()` + `relative_to()`로 **경로 탈출을 차단**한다(위반 시 403).
- `web/dist` 자체가 없으면 `503 {"error": "web_not_built", "hint": "cd web && npm install && npm run build"}`.
- `.html`은 `Cache-Control: no-store` → **컨테이너 재시작 없이** 파일만 갱신하면 반영된다.

## 6. 보안 모델 (한계를 분명히)

- 위협 모델은 "관람객이 남이 조작 중인 PTZ를 실수로 건드림" 수준이다. 악의적 공격자를
  가정하지 않았다.
- 조회·스트림은 무인증이고, PIN은 평문 하드코딩이며, 현재 데모 페이지 구성에서는
  조작까지 사실상 무인증이다.
- **로컬 LAN 전용.** 공개 인터넷에 노출하지 말 것. 시연 전 PIN 교체 권장.
