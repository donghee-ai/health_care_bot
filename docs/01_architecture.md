# 시스템 아키텍처

본 문서는 본 라인이 **어떤 단위로 실행되고, 무엇이 무엇에 의존하고, 어떤 상태를 누가
소유하고, 무엇이 고장나면 어떻게 되는지**를 정리합니다. 코드를 고치기 전에 경계와
degrade 규칙을 정확히 알도록 작성합니다.

- HTTP 계약·`stats.json` 스키마: [`02_http_api_and_stats.md`](02_http_api_and_stats.md)
- 추적/카운팅 알고리즘: [`03`](03_algorithm_ptz_tracking.md) · [`04`](04_algorithm_exercise.md)
- 실행·배포 절차: [`07_runbook.md`](07_runbook.md)
- 성능 실측: [`09_performance_roadmap.md`](09_performance_roadmap.md)

## 0. 한 눈에 — 컨테이너 1개, 프로세스 1개

```
UNO Q (Linux, arm64)
└── docker: health-care-bot:22.04   --net host, -v $PWD:/work
    └── python3 /work/src/main.py            ← 프로세스 딱 하나
        ├── [스레드] FrameGrabber            카메라 read 전용
        ├── [스레드] 메인 추론 루프           invoke → 각도 → 카운터 → PTZ → encode
        ├── [스레드] HTTP accept 루프         http.server + ThreadingMixIn
        └── [스레드] 커넥션당 1개             /stream.mjpg는 연결이 살아있는 동안 점유
```

**웹 프론트엔드에는 런타임이 없다.** 배포 UI(`web/app/index.html`)는 자체포함 정적
HTML 한 장이라 빌드 단계 자체가 없고, 컨테이너는 그 파일을 읽어 내보낼 뿐이다.
React 시안(`web/src/`)을 빌드할 때만 개발 PC에서 Vite를 돌린다 — 컨테이너 이미지에
Node가 아예 없다.

## 1. 스레드 모델

| 스레드 | 소유 | 하는 일 | 주기 |
|---|---|---|---|
| 메인 | `main.py::main` | grab → letterbox → invoke → 각도/카운터 → PTZ → draw → encode → stats | ~90 ms (11 FPS) |
| FrameGrabber | `main.py::FrameGrabber` | `cap.read()`를 계속 돌려 **최신 프레임 1장만 덮어쓰기** | 카메라 속도 (~33 ms) |
| HTTP accept | `http_server.py::start_server` | 소켓 accept → 커넥션마다 스레드 생성 | 이벤트 |
| MJPEG 커넥션 | `_Handler::_stream_mjpg` | 최신 JPEG를 multipart로 밀어냄 + 뷰어 수 카운트 | 30 ms sleep |

메인 루프는 `frame_id`가 그대로면 5 ms 대기하고 넘어간다 — 같은 프레임을 두 번 추론하지
않으면서 바쁜 대기로 코어를 태우지도 않는다.

### 1-1. 왜 캡처 스레드를 분리했나

추론 루프(~90 ms)가 카메라(~33 ms)보다 느리면 드라이버 버퍼에 안 읽힌 프레임이 쌓여
**지연이 계속 누적된다.** `cv2.CAP_PROP_BUFFERSIZE=1`은 V4L2/UVC 드라이버가 무시하는
경우가 흔해 안전장치가 못 된다. 큐가 아니라 "최신 1장 덮어쓰기"로 바꿔 처리 프레임의
나이를 "루프 1회분"으로 고정했다.

> **지연(latency)과 처리량(FPS)은 다른 지표다.** FrameGrabber는 지연만 고쳤고 FPS는
> 그대로다(10.8 ±4 → 동일). 회귀가 아니라 의도된 결과다.
> 상세: [`issues/2026-07-11_04`](issues/2026-07-11_04_camera_buffer_accumulation_causes_growing_latency.md)

## 2. 프레임 파이프라인

```
grabber.latest()            최신 프레임 (BGR, 640x480)
  → letterbox_square(256)   비율 유지 + pad 114 → 256x256
  → BGR2RGB, uint8, [1,256,256,3]
  → interpreter.invoke()    MoveNet Thunder INT8 (4 threads)          ★ 지배적
  → raw [1,1,17,3]
  → unletterbox_kp()        원본 픽셀 좌표계 (y, x, conf) 17개
  ├─ body_orientation()     표시용만 (분류에는 더 이상 안 씀)
  ├─ select_counter(mode)   app_state.get_mode() → squat | overhead | lateral
  ├─ person_center_*()      stats/오버레이용 중심점 (PTZ 추적점과 별개)
  ├─ ptz.set_track_mode(exercise); ptz.update(kp, h, w, now_ms)
  ├─ compute_angle() → counter.update(angle, now_ms) → rep 이벤트
  ├─ draw_pose()            스켈레톤 + 점 + 종목별 강조
  └─ update_live_state()    JPEG 인코딩(q=70) + stats dict 교체
```

### 2-1. 좌표계 주의

MoveNet 출력과 `pose_utils`의 keypoint 배열은 **`(y, x, conf)` 순서**다. 정규화
헬퍼(`*_center_normalized`)는 **`(x_norm, y_norm)`으로 뒤집어서** 반환한다.
PTZ·stats는 정규화 좌표를 쓰고, 그리기는 픽셀 좌표를 쓴다. 두 규약을 섞으면 좌우/상하가
조용히 바뀐다.

### 2-2. 영상에 숫자를 굽지 않는다

FPS/각도/REPS/PTZ는 웹 UI가 `stats.json`으로 이미 표시하므로 `putText` 오버레이를 전부
제거했다. 스켈레톤만 남긴다 — 중복 제거 + 인코딩 비용 절감.

## 3. 모듈 경계와 의존 방향

```
                        main.py  (유일한 조립 지점)
        ┌──────────┬──────────┬─────────┴────┬────────────┬──────────┐
        v          v          v              v            v          v
  pose_utils    angles   exercise_counter  ptz_controller  http_server  app_state
        ^          |            guard_capture     |            |          ^
        └──────────┘                              v            └──────────┘
     (angles가 KP 상수만 참조)              st3215_bus        (init_app 주입)
                                                 |
                                             pyserial
```

원칙:

- **의존은 한 방향으로만 흐른다.** `pose_utils`·`angles`·`exercise_counter`는 순수 계산
  모듈이다. 서보도, HTTP도, 세션도 모른다.
- **`app_state`는 추론과 무관한 순수 상태 객체다.** 모드 전환은 `app_state`에 값을 쓰고,
  추론 루프가 매 프레임 `get_mode()`로 **읽어가는** 방향이다 — 웹이 추론 루프를 호출하지
  않는다.
- `st3215_bus`는 프로토콜만 아는 저수준 드라이버다. 추적 로직이 없어서 벤치
  스크립트(`scripts/test_st3215_serial.py`, `calibrate_st3215.py`)와 공유된다.

### 3-1. 의존성 주입 — `init_app()`

`http_server`는 추론 루프 객체를 **직접 import하지 않는다.** `main.py`가

```python
init_app(ptz=ptz, squat_c=..., overhead_c=..., lateral_c=..., avg_fps_fn=...)
```

로 참조를 주입하고, 핸들러는 모듈 전역에 담긴 그 참조로만 접근한다. 덕분에 카메라·모델
없이 `scripts/mock_serve.py`로 프론트만 검증할 수 있다.

## 4. 상태 소유권

"누가 진짜 주인인가"를 헷갈리면 버그가 난다.

| 상태 | 주인 | 수명 | 비고 |
|---|---|---|---|
| rep 카운터 3개 | `main.py` 지역 변수 | 프로세스 | HTTP에는 참조만 넘김. **3개가 항상 동시에 살아 있다** |
| 서보 목표각 `pan_deg`/`tilt_deg` | `PTZController` | 프로세스 | 서보의 실제 위치가 아니라 **우리가 명령한 각도** |
| 추적 스무딩·복구 단계 | `PTZController` 내부 필드 | 프로세스 | 재검출 시 `_reset_recovery()`로 통째 취소 |
| 세션(mode/status/target) | `app_state._session` | 프로세스 | DB 없음. 재시작 시 초기화 |
| 경비 모드 무장/쿨다운/수동촬영 | `app_state._guard` | 프로세스 | 촬영 **파일**은 `captures/`에 영구 |
| 운영자 제어권 lock | `app_state._control_*` | 60초 (heartbeat 연장) | 재시작 시 초기화 → 좀비 lock이 안 남는 게 오히려 안전 |
| 최신 JPEG / stats | `http_server` 모듈 전역 + `_state_lock` | 다음 프레임까지 | 뷰어 수는 별도 lock |

**모드의 진짜 주인은 `app_state`다.** `--mode` CLI 값은 시작 시 한 번 밀어넣는 초기값일
뿐이고, `--serve`가 켜져 있으면 이후 매 프레임 `app_state.get_mode()`가 이긴다.

## 5. 서보 제어 경로

```
ptz_controller.update()      추적 판정 → 목표각(deg) 결정
  → _write(servo_id, deg)
     → st3215_bus.write_pos_ex(ser, id, deg, speed=569, acc=20)
        → deg * (4095/360) → tick, 0~4095 클램프
        → Feetech STS 패킷 [0xFF 0xFF id len INST_WRITE ADDR_ACC ...] + checksum
        → pyserial write (1 Mbaud) → 어댑터 → 버스 → 서보
```

### 5-1. 코드에 박힌 안전 규칙

1. **소프트리밋 클램프** — 자동 추적·수동 조작·복구 동작 **모든 경로**가
   `_clamp(..., yaw_min, yaw_max)`를 통과한다. 기구부에 부딪히며 밀어붙이는 상황을
   코드 레벨에서 차단.
2. **속도 고정** — `servo_speed=569`(≈50 deg/s)를 모든 명령에 실어 보낸다. 목표각이
   아무리 멀어도 그 속도 이상으로 돌지 않는다(손가락 끼임 방지).
3. **torque ON 순서** — `_torque_on_safe()`가 *현재 위치를 읽어 goal로 먼저 쓴 뒤*
   torque를 켠다. 안 그러면 켜지는 순간 옛 goal로 점프한다.
4. **기동 시 중앙 정렬** — 이전 실행에서 틀어져 있어도 항상 180/180에서 시작하고,
   이동 거리에 비례한 settle 시간을 계산해 대기한다.
5. **EEPROM은 런타임에 절대 안 건드린다.** `Homing_Offset` 조작은 캘리브레이션 스크립트
   전용이다 — torque on 상태에서 바꾸면 실제 회전이 일어나 부품이 깨진다(실기 사고 이력:
   [`issues/2026-07-17_01`](issues/2026-07-17_01_homing_offset_wrong_sign_bit_caused_physical_snap.md)).

## 6. 실패 / degrade 경로

**원칙: 없어도 되는 것이 없으면 기능만 줄이고, 있어야 하는 것이 없으면 즉시 죽는다.**
"반쯤 동작하는데 왜 안 되는지 모르는" 상태를 만들지 않는다.

| 무엇이 없거나 실패 | 결과 | 기동 로그 |
|---|---|---|
| 모델 파일 | **즉시 종료** | `ERROR: model not found` |
| 카메라 열기 실패 | **즉시 종료** | `ERROR: cannot open camera /dev/videoN` |
| HTTP 포트 바인딩 실패 | **즉시 종료** | `ERROR: failed to start HTTP server` |
| `--serial` 미지정 | PTZ **disabled** (추적 계산만) | `[ptz] serial_port 미지정 - disabled` |
| pyserial 없음 | PTZ disabled | `[ptz] st3215_bus 사용 불가` |
| 포트 열기 실패 | PTZ disabled | `[ptz] 포트 열기 실패 (...)` |
| **서보 무응답** (전원 없음/배선) | PTZ disabled | `[ptz] 서보 무응답 (...) - 서보 전원/버스 케이블 확인` |
| 서보 쓰기 오류 (런타임) | 해당 명령만 실패, 카운트 안 됨 | `[ptz] 서보 쓰기 오류` |
| `web/app`·`web/dist` 둘 다 없음 | `/app`이 503 + 힌트 (`web/app`은 커밋되므로 정상 클론에선 발생 안 함) | (요청 시) |
| `captures/` 쓰기 실패 | 해당 촬영만 실패, 경비 모드는 계속 | `[guard]` 로그 없음 |
| `/proc`·`/sys` 없음 (PC) | 텔레메트리 필드가 `null` | 없음 |
| keypoint conf 미달 | 각도 `None` → 카운터는 상태 유지하고 넘어감 | 로그 `L=? R=?` |
| 미검출 지속 | PTZ 복구 사다리 진행 | 로그 `COAST`/`BACK`/`CENTER` |

> **PTZ disabled는 조용하다.** 한 줄 경고 뒤 정상 실행이 계속되므로 "PTZ만 왜 안 되지"로
> 헤매기 쉽다. **기동 로그의 `serial :` 줄을 먼저 보는 습관**이 결국 답이다.

## 7. 구조적 제약

| 제약 | 이유 | 완화 |
|---|---|---|
| FPS ~11 천장 | invoke 바운드, INT8 dotprod 명령 없음 | NPU 델리게이트 (미착수) |
| CPU 여유 17% | 추론+인코딩이 대부분 사용 | 추가 워크로드는 이 여유를 나눠 써야 함 |
| 세션·제어권이 재시작 시 소실 | in-memory, DB 없음 | 시연 성격상 허용 |
| 다중 동시 접속 미검증 | `/stream.mjpg`가 커넥션당 스레드 1개를 영구 점유 | 뷰어 수 실측 안 됨 |
| 500 ms 폴링 지연 | `http.server`와 WebSocket 궁합이 나쁨 | 필요해지면 FastAPI+SSE |
| **서보 실제 위치를 안 읽는다** | 매 프레임 read하면 버스 왕복이 늘어남 | 목표각과 실제각이 어긋나도 감지 못 함 |
| MCU 미사용 | raw serial 경로 없음 + 배선 불가 | 보류 |

### 7-1. 코드에 남은 낡은 것 (동작에 영향)

- ~~`docker/Dockerfile`의 `CMD`가 오래됐다~~ — `--mode auto`라 `run.sh` 없이
  `docker run`만 하면 `invalid choice: 'auto'`로 즉시 종료됐다.
  **2026-09-09에 `--mode squat`으로 정정**(run.sh가 넘기던 값과 동일).
- **`st3215_bus.py::set_id` docstring**이 "실제 반영은 전원 재투입 후"라고 적고 있는데,
  실기에서는 **즉시 반영**된다
  ([`issues/2026-07-16_01`](issues/2026-07-16_01_servo_id_change_takes_effect_immediately.md)).
- ~~`pose_utils.py`·`exercise_counter.py`·`angles.py`·`main.py`·`Dockerfile` 주석의
  "squat + pushup" 옛 표현~~ — **2026-09-09 정리**. `angles.py`의
  `classify_orientation`은 pushup 시절 유물이지만 함수 자체가 아직 쓰이므로
  docstring에 그 경위를 남겨뒀다.
