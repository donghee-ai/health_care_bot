# 2026-07-19 — 디바이스 코드 동기화 (07-17 PTZ 통합분 반영)

## 시점

2026-07-19 (PC에서 PTZ 통합 검증 완료 후, UNO Q 실기 배포 준비)

## 사건

adb로 UNO Q(`1204329696`)에 접속해 07-15~17 작업분을 push. 코드 동기화만
수행했고 컨테이너 기동은 하지 않음.

## 배경

디바이스 코드가 **07-11/07-14 상태에 멈춰 있었다.** 07-15 이후 작업
(FrameGrabber 지연 수정, ST3215 드라이버, PTZ v1/v2, 웹 파이프라인 통합)이
전혀 반영돼 있지 않았음. 특히:

- `st3215_bus.py`가 **디바이스에 아예 없었다** — `ptz_controller.py`가 import
  하므로 이 상태로 기동했으면 import 에러로 즉시 크래시
- `ptz_controller.py` 8,545 bytes (Jul 11 구버전) → v2 로직 이전
- `pose_utils.py` 3,055 bytes (Jul 5) → 무릎/엉덩이 중심점 헬퍼 없음

## 결과

- `src/`(9개), `docker/`(3개), `scripts/`(8개) push 완료
- **md5로 15개 파일 전부 로컬과 일치 확인** (push 로그만 믿지 않음)
- `web/dist`는 디바이스에 이미 최신본 존재(해시 일치) — 07-11 이후 프론트
  변경 없어 재빌드/재push 불필요
- `models/movenet_thunder_int8.tflite`는 로컬·디바이스 동일(7,126,768) — 미전송
- 디바이스에서 `python3 -m py_compile src/*.py` → `COMPILE OK` (문법만 검증,
  런타임 동작 보장 아님)

기존 함정 2건은 그대로 적용해 회피:
PowerShell로만 실행([`2026-07-11_01`](../issues/2026-07-11_01_adb_push_msys_path_mangling.md)),
디렉토리 push 전 remote `rm -rf`([`2026-07-11_02`](../issues/2026-07-11_02_adb_push_directory_nests_when_remote_exists.md)).

## 실행을 막고 있는 것 (하드웨어, 코드 문제 아님)

기동을 시도하지 않은 이유. 둘 다 07-11과 동일한 상태:

- **UVC 카메라 없음** — `v4l2-ctl --list-devices` 결과 `/dev/video0`·`/dev/video1`은
  Qualcomm Venus 인코더/디코더 노드뿐. 카메라 노드 자체가 없음. 이 상태로
  컨테이너를 띄우면 `cannot open camera`로 즉시 종료된다.
  (adb 연결 중에는 허브를 꽂을 수 없어 카메라를 물리지 못한 상황)
- **서보 어댑터 없음** — `/dev/ttyUSB*`·`/dev/ttyACM*` 둘 다 없음. CH343
  어댑터가 개발 PC의 COM9에 물려 있어 UNO Q 쪽엔 연결돼 있지 않다. PTZ는
  설계대로 disabled 폴백.

## 다음 단계

1. USB 카메라 연결 후 `v4l2-ctl --list-devices`로 `Video Capture` 타입 노드
   확인 (Venus가 0·1을 선점하므로 보통 `/dev/video2` 이상)
2. CH343 어댑터를 UNO Q로 이설 후 `ls /dev/ttyUSB*`로 노드 확인
3. `CAMERA_DEV=/dev/videoN bash docker/run.sh`로 기동, 라이브 스트림 e2e 검증
