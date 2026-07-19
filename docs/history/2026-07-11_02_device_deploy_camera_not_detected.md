# 2026-07-11 — 디바이스 배포 확인 + USB 카메라 미인식 발견

## 시점

2026-07-11 (웹앱 MVP 구현 직후)

## 사건

adb로 실제 UNO Q(`unoq-korea01`)에 접속해 오늘 변경분(백엔드 API + `web/dist`)을
push하고 컨테이너를 기동해 `/app` 정상 서빙을 로그로 확인. 다만 카메라
캡처 단계에서 실패해 컨테이너가 즉시 종료됨.

## 배경

디바이스의 `/home/arduino/health_care_bot/`이 2026-07-05 상태로 멈춰있어
(`app_state.py` 없음, `web/` 폴더 없음, `http_server.py` 132줄 구버전)
오늘 만든 웹앱이 전혀 반영돼 있지 않았다. 실제 동작 확인을 위해 push +
컨테이너 기동까지 진행.

## 결과

- push (adb) 성공, `/app`·`/app?role=operator` URL이 서버 로그에 정상 출력 —
  새 백엔드 코드가 실제 디바이스에서 정상 동작함을 확인
- `docker run`이 `/dev/video0`를 열지 못하고 `ERROR: cannot open camera`로 종료
- `v4l2-ctl --list-devices`로 확인한 결과 `/dev/video0`·`/dev/video1`은 USB
  카메라가 아니라 **Qualcomm Venus 하드웨어 비디오 코덱(디코더/인코더)**
  노드였음 — 즉 USB UVC 카메라가 현재 디바이스에 물려있지 않거나 인식이
  안 된 상태. `unoq-companion-robot/pose` 문서에 이미 기록된 것과 동일한
  증상 패턴 (Venus 코덱 노드 vs UVC 카메라 구분).
- PTZ 시리얼(`/dev/ttyACM0`)도 현재 없음 — PTZ는 정상적으로 disabled 모드로
  fallback (에러 아님, 설계대로 동작).

## 다음 단계

USB 카메라 재연결 + 필요 시 `sudo modprobe -r uvcvideo && sudo modprobe uvcvideo`
후 `v4l2-ctl --list-devices`로 `Video Capture (single-plane)` 타입 노드가
보이는지 재확인. 그 후 컨테이너 재기동해 라이브 스트림 e2e 검증.
