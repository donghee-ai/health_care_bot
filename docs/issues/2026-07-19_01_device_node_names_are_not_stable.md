# 디바이스 노드 이름(`/dev/video*`, `/dev/tty*`)은 고정이 아니다 — 실행 전 매번 확인

## 증상

### 카메라 — 문서에 적힌 규칙이 반대로 뒤집힘

기존 문서(HANDOFF, `docker/run.sh` 주석)에 이렇게 적혀 있었다:

> Qualcomm Venus 코덱이 `/dev/video0`·`video1`을 먼저 차지하므로 보통
> `/dev/video2` 이상이 진짜 카메라

2026-07-19 실측은 **정반대**였다.

```
USB 2.0 Camera: HD USB Camera (usb-xhci-hcd.2.auto-1.2):
        /dev/video0
        /dev/video1

Qualcomm Venus video decoder:  /dev/video2
Qualcomm Venus video encoder:  /dev/video3
```

문서를 믿고 `CAMERA_DEV=/dev/video2`로 기동했다면 Venus 디코더를 카메라로
열려다 실패했을 것이다. `v4l2-ctl -d /dev/video2 --info`로 확인한 결과
드라이버가 `qcom-venus`, Device Caps가 `Video Memory-to-Memory Multiplanar`
였다 — 캡처 장치가 아니다.

| 관측 시점 | USB 카메라 | Venus 코덱 |
|---|---|---|
| 2026-07-11 | (연결 없음) | video0·1 |
| 2026-07-19 | **video0·1** | video2·3 |

### 서보 어댑터 — ttyUSB가 아니라 ttyACM

`run.sh`의 기본값과 문서가 모두 `/dev/ttyUSB0`이었으나, 실제로는
**`/dev/ttyACM0`** 으로 잡힌다. `/dev/ttyUSB*`는 아예 존재하지 않는다.

```
crw-rw---- 1 root dialout 166, 0 Jul 19 03:39 /dev/ttyACM0
```

`lsusb`상 `1a86:55d3 QinHeng Electronics USB Single Serial` (CH343).

## 원인

**노드 번호는 부팅 시 드라이버 등록 순서로 결정된다.** 그 순서는
USB를 어느 포트에 꽂았는지, 어떤 순서로 꽂았는지, 부팅 시점에 무엇이
연결돼 있었는지에 따라 달라진다. 07-11에는 카메라가 연결돼 있지 않아
Venus가 0·1을 가져갔고, 07-19에는 부팅 시점에 카메라가 물려 있어 먼저
등록됐다.

**시리얼은 드라이버 종류의 문제다.** CH343은 vendor 드라이버(ch341 계열)로
잡히면 `ttyUSB`, CDC-ACM 표준 드라이버로 잡히면 `ttyACM`이 된다. UNO Q
커널은 CDC-ACM 쪽이다.

즉 **어느 쪽도 "보통 이 번호"라는 규칙이 성립하지 않는다.** 특정 시점의
관측을 규칙으로 일반화한 것이 원래 문서의 오류였다.

## 영향

- **카메라**: 잘못된 노드를 지정하면 컨테이너가 카메라를 못 열고 즉시 종료
- **서보**: 노드를 못 찾으면 `run.sh`의 `[ -e "${SERIAL_DEV}" ]` 검사에서
  걸러져 `--device` 인자 없이 실행되고, PTZ는 설계대로 disabled로 degrade
  한다. 기동 로그에 `(MISSING — PTZ disabled)`가 출력되기는 하지만 한 줄이라
  놓치기 쉽고, 그대로 계속 실행되므로 "PTZ만 왜 안 되지"로 헤매게 된다

## 해결

**실행 직전에 매번 확인한다. 문서의 번호를 그대로 쓰지 않는다.**

```bash
v4l2-ctl --list-devices          # USB ... Camera 로 표시된 쪽이 진짜 카메라
ls /dev/ttyACM* /dev/ttyUSB*     # 양쪽 다 볼 것
```

`docker/run.sh`도 함께 고쳤다:

- `SERIAL_DEV` 미지정 시 `/dev/ttyACM*` -> `/dev/ttyUSB*` 순으로 **자동 탐색**
- 카메라/시리얼 노드가 없으면 기동 시 **눈에 띄는 경고 블록**을 출력
  (기존의 한 줄짜리 `(MISSING)` 표기는 스크롤에 묻혔다)
- 주석에서 "보통 video2 이상" 규칙을 삭제하고 매번 확인하도록 변경

## 재발 방지

- **디바이스 노드 번호를 문서에 "규칙"으로 적지 않는다.** 특정 시점의 관측은
  관측으로만 기록하고(위 표처럼 날짜와 함께), 판별 방법을 적는다
- 카메라 노드는 번호가 아니라 **`v4l2-ctl --list-devices`의 장치 이름**으로
  식별한다. `Qualcomm Venus`는 코덱이지 카메라가 아니다
- 시리얼은 `ttyACM`/`ttyUSB` **양쪽을 항상 확인**한다
- 기동 후 PTZ가 안 움직이면 하드웨어를 의심하기 전에 **기동 로그의 serial
  줄부터** 본다
