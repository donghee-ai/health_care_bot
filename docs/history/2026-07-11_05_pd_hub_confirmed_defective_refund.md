# 2026-07-11 — PD 허브 데이터 결함 진단 → PC 재연결로 초기화하면 해결됨

## 시점

2026-07-11

## 사건

카메라가 안 잡히던 문제(`docs/issues/2026-07-11_02_device_deploy_camera_not_detected.md`에서
처음 발견)를 SSH로 원격 진단한 끝에, 원인이 카메라가 아니라 **PD 허브가
전원 공급(PD)과 USB 데이터 허브 역할을 동시에 수행하지 못하는 하드웨어/
협상 문제**로 좁혀졌다. 이후 실제로 **허브를 PC에 한번 꽂았다 뺐더니
허브가 초기화(재협상)되면서, 다시 UNO Q에 연결했을 때 카메라가 정상
인식**되는 것을 확인 — 이 재연결 트릭으로 **문제 해결**. 상세 진단 과정과
배제한 가설들은
[`docs/issues/2026-07-11_03_usb_camera_not_detected_via_pd_hub.md`](../issues/2026-07-11_03_usb_camera_not_detected_via_pd_hub.md)
참고.

## 배경

UNO Q는 USB-C 포트가 하나뿐이고(USB-A 등 별도 호스트 포트 없음), 그
포트에 PD 허브를 물려 보드 전원 공급과 카메라 연결을 동시에 하는 구성으로
운용 중이었다. 물리적으로 케이블을 뽑으면 보드 전체가 죽어 SSH 세션도
끊기는 제약 때문에, 재현 테스트 없이 순수 sysfs/dmesg 로그 분석만으로
진단을 진행 — `/sys/class/typec/port0/{power_role,data_role}` 확인으로
보드 쪽 role 협상은 정상임을 먼저 확인했고, 카메라 대신 단순 USB
저장장치로 교차검증해 카메라 특정 문제가 아님을 좁혔다. 같은 허브를 PD
없이 일반 PC에 연결했을 때 데이터가 정상 동작하는 것도 확인 — 허브의
데이터 라인 자체는 멀쩡함을 재확인했다.

## 결과

- **허브가 이상한 상태로 멈춰있을 때 PC에 한 번 물렸다 빼면 초기화되고,
  그 상태로 다시 UNO Q에 꽂으면 카메라가 정상 인식된다.** 매번 재부팅마다
  또는 USB 재연결 시마다 이 증상이 재발할 가능성은 있음 — 완전히 근본
  수정된 하드웨어 결함이라기보다는, 허브가 특정 negotiation 상태에서
  멈추는 걸 PC 재연결이 리셋시켜주는 워크어라운드에 가까움. 재발 시
  같은 방법(PC에 재연결 후 UNO Q로)으로 대응.
- health_care_bot 웹앱(백엔드 API + `web/dist`)은 이미 디바이스에 정상
  배포·기동 확인됨.
- 같은 세션에서 카메라 지연 문제(FPS 10.8, 체감 지연 loop_ms보다 훨씬 김)도
  발견돼 `src/main.py`에 `FrameGrabber`(캡처 전용 스레드, 최신 프레임만
  유지) 적용 + `docker/run.sh`에 `CAMERA_INDEX` 자동 매핑 추가 — 디바이스에
  push 완료, 카메라 재인식 후 실측 필요.

## 다음 단계

카메라가 다시 인식되면: (1) `lsusb`/`v4l2-ctl --list-devices`로 UVC 카메라
노드 확인 → (2) `CAMERA_DEV=/dev/videoN bash docker/run.sh`로 `main.py`
재기동(수정된 FrameGrabber 포함) → (3) `/stats.json`의 `fps`/`loop_ms`로
지연 개선 확인 → (4) 웹앱 `/app`에서 실제 라이브 스트림 체감 지연 e2e 확인
(`docs/history/2026-07-11_01_web_app_mvp_built.md` "다음 단계"와 연결).
