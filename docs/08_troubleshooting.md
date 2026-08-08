# 트러블슈팅 · 함정 색인

본 문서는 **증상에서 원인으로 가는 길**을 모아둔 색인입니다. 각 항목은 요약만 담고, 상세
경위는 `issues/`의 해당 파일로 넘깁니다. 같은 함정을 두 번 밟지 않는 것이 목적입니다.

## 0. 증상에서 시작하기

| 증상 | 가장 흔한 원인 | 절 |
|---|---|---|
| 컨테이너가 뜨자마자 죽는다 | 카메라 노드 오지정 / argparse 인자 불일치 | §1 |
| 폰만 접속이 안 된다 | 폰 랜덤 MAC | §2 |
| 카메라·서보가 **둘 다** 안 잡힌다 | 허브 전원(호스트 VBUS) | §3 |
| PTZ만 안 움직인다 | 시리얼 노드 미검출 → disabled | §4 |
| 서보 ID 전부 무응답 | 서보 외부전원 없음 | §4 |
| 영상이 매끄러운데 지연이 크다 | 카메라 버퍼 누적 | §5 |
| 코드를 밀었는데 반영이 안 된다 | adb push 중첩 / Git Bash 경로 변환 | §6 |
| 웹을 고쳤는데 안 바뀐다 | `npm run build`가 Fluid를 덮음 | §6 |
| 콘솔에서 `UnicodeEncodeError` | cp949 콘솔 + em-dash·이모지 | §7 |

## 1. 기동 실패 / 즉시 종료

| 함정 | 요약 |
|---|---|
| **카메라 노드 오지정** | `Qualcomm Venus`(코덱) 노드를 카메라로 열려다 실패 → `cannot open camera`로 즉시 종료. 노드 번호는 부팅마다 바뀐다. 이름으로 식별할 것 → [`issues/2026-07-19_01`](issues/2026-07-19_01_device_node_names_are_not_stable.md) |
| **argparse choices ↔ 하드코딩 인자 불일치** | `--mode`에서 `auto`를 없앴는데 `run.sh`가 `--mode auto`를 넘겨 컨테이너가 즉시 종료됐다(`invalid choice`). run.sh는 고쳤지만 **`docker/Dockerfile`의 `CMD`에 아직 `--mode auto`가 남아 있다** → `run.sh` 없이 `docker run`하면 같은 증상 |
| **`--rm`이라 로그가 안 남는다** | 죽은 컨테이너는 `docker logs`에 없다. `bash docker/run.sh > /tmp/hcb_run.log 2>&1`로 캡처 |
| 모델 파일 없음 | `ERROR: model not found` → `bash scripts/copy_model.sh` |

## 2. 네트워크 · 접속

**크롬 에러 메시지로 원인을 먼저 가른다:**

| 에러 | 의미 | 원인 방향 |
|---|---|---|
| **`ERR_ADDRESS_UNREACHABLE`** | 대상 IP로 가는 **경로 없음** | 폰이 그 서브넷 밖 — 랜덤 MAC / 셀룰러 폴백 / 다른 SSID |
| `ERR_CONNECTION_TIMED_OUT` | 경로는 있는데 응답 없음 | AP 클라이언트 격리 / 방화벽 |
| `ERR_CONNECTION_REFUSED` | 닿았는데 포트 닫힘 | 서버 미기동 / 포트 오류 |

`ADDRESS_UNREACHABLE`는 **서버·네트워크 문제가 아니라 폰이 그 LAN에 실제로 안 붙어 있다는
신호**다. 실제로 이 증상에서 웹 버전 롤백까지 시도했으나 원인은 폰이었다.

**폰 쪽 진단 순서**: ① 모바일 데이터 OFF(로봇 Wi-Fi에 인터넷이 없으면 LTE로 새어나간다) →
② 다른 폰과 **정확히 같은 SSID**(…5G/guest/중계기 아님) → ③ 폰 IP가 `192.168.0.x`인지 →
④ Wi-Fi 잊기·재접속("인터넷 없음, 연결 유지?" → 유지) → ⑤ **랜덤 MAC OFF** →
⑥ VPN/사설DNS OFF.

> **데모 당일**: 참석자 폰도 같은 함정에 걸릴 수 있다. 접속 안 되는 폰은 "그 네트워크에서
> 랜덤 MAC 끄기"를 먼저 안내할 것.
> 상세: [`issues/2026-07-26_01`](issues/2026-07-26_01_mobile_web_access_fails_random_mac.md)

## 3. USB · 장치 인식

| 함정 | 요약 |
|---|---|
| **호스트 VBUS가 꺼져 있다** | UNO Q는 `usb_vbus=disabled`(단 `usb_role=host`)라 **버스파워 허브/장치는 enumeration 자체가 안 된다**(`lsusb`에 루트 허브만). **셀프파워 허브 필수.** 카메라·서보가 *둘 다* 안 잡히면 개별 장치가 아니라 허브 전원부터 의심 |
| **PD 허브 데이터 라인 미인식** | PD 전원 공급 중에는 데이터 허브 역할을 못 하던 개체. **허브를 PC에 한 번 꽂았다 빼면 초기화되어** 정상 인식 → [`issues/2026-07-11_03`](issues/2026-07-11_03_usb_camera_not_detected_via_pd_hub.md) |
| 노드 번호 변동 | `/dev/videoN`·`ttyACM/ttyUSB`가 부팅마다 바뀐다 → [`issues/2026-07-19_01`](issues/2026-07-19_01_device_node_names_are_not_stable.md) |

**진단 명령**:

```bash
for r in /sys/class/regulator/*/; do echo "$(cat $r/name)=$(cat $r/state)"; done | grep -i usb
cat /sys/class/usb_role/*/role
lsusb                                    # 외장 허브가 보이는지
dmesg | grep -iE "vbus|cdc_acm|new .*USB device"
```

정상이면 `lsusb`에 `ARC Camera` + `QinHeng CH343` + `Huasheng HUB`가 보인다.

## 4. 서보 · PTZ

| 함정 | 요약 |
|---|---|
| **서보 외부전원 없음** | 전원(6~12.6V)이 없으면 포트는 정상으로 열리는데 **ID 전부 무응답**. COM 포트/ID 문제로 오해하기 쉽다 → **어댑터 배럴잭 먼저** |
| **PTZ disabled가 조용하다** | 시리얼 노드를 못 찾으면 한 줄 경고 뒤 정상 실행이 계속된다. 기동 로그의 `serial :` 줄부터 볼 것 |
| **torque ON 상태 EEPROM 변경 금지** | offset을 torque 켠 채 바꾸면 옛 `Goal_Position`으로 실제 회전 → **3D 출력물 파손 이력.** `calibrate` 명령을 쓸 것 → [`issues/2026-07-17_01`](issues/2026-07-17_01_homing_offset_wrong_sign_bit_caused_physical_snap.md) |
| **부호비트 위치가 레지스터마다 다르다** | `Homing_Offset`=bit11, `Present_Position`=bit15. 양수는 우연히 같아 정상처럼 보이고 **음수에서 터진다** |
| **서보 ID 변경은 즉시 반영** | "전원 재투입 필요"라는 일반 SDK 문구와 다르다. `set-id` 실패 로그가 떠도 새 ID로 `ping`해 확인 → [`issues/2026-07-16_01`](issues/2026-07-16_01_servo_id_change_takes_effect_immediately.md) |
| 공장 출하 ID 충돌 | ST3215는 전부 ID=1이다. **체인 연결 전에 낱개로** 1/2를 나눠 기록 |
| 목표각 ≠ 실제각 | 런타임에 서보 위치를 읽지 않으므로 어긋나도 감지 못 한다. 의심되면 `test_st3215_serial.py --id N read` |

절차: [`06_hardware_calibration.md`](06_hardware_calibration.md)

## 5. 카메라 · 영상

| 함정 | 요약 |
|---|---|
| **`cv2.CAP_PROP_BUFFERSIZE`를 믿지 말 것** | V4L2/UVC 드라이버가 무시하는 경우가 흔하다. 캡처가 처리보다 빠르면 버퍼에 프레임이 쌓여 **지연이 계속 커진다**. `FrameGrabber`(최신 1장만 유지)로 해결됨 → [`issues/2026-07-11_04`](issues/2026-07-11_04_camera_buffer_accumulation_causes_growing_latency.md) |
| "매끄럽다 ≠ 지연 없다" | 큐 기반 파이프라인은 매끄러우면서 지연이 계속 커질 수 있다. `loop_ms`로 설명 안 되는 체감 지연이면 버퍼 누적을 의심 |
| FPS와 지연은 다른 지표 | 지연을 고쳤다고 FPS가 오르지 않는다. FPS는 추론/인코딩 자체를 빠르게 해야 오른다 → [`09`](09_performance_roadmap.md) |
| 카메라 레이트 캡이 안 먹는다 | 15fps 캡을 시도해도 카메라가 무시하고 30.5를 유지한 사례 있음 |
| 스트림 첫 프레임이 늦다 | `--idle-skip-draw`로 실행 중이고 뷰어가 0명이었으면 정상 |

## 6. 배포 · 반영 안 됨

| 함정 | 요약 |
|---|---|
| **Git Bash로 adb push** | MSYS가 리모트 경로를 Windows 경로로 변환해 **조용히 실패**한다. **PowerShell로** → [`issues/2026-07-11_01`](issues/2026-07-11_01_adb_push_msys_path_mangling.md) |
| **디렉토리 push 전 remote `rm -rf`** | remote 경로가 이미 있으면 `src/src/`·`dist/dist/`로 중첩된다. 구버전이 서빙돼 "반영 안 됨"으로 보임 → [`issues/2026-07-11_02`](issues/2026-07-11_02_adb_push_directory_nests_when_remote_exists.md) |
| push 로그를 믿지 말 것 | `md5sum`으로 대조 |
| **`npm run build`가 Fluid를 덮는다** | `/app`은 자체포함 정적 HTML이라 React 빌드 대상이 아니다 → [`05`](05_web_ui_fluid.md) §9-1 |
| **SSH 세션 안에서 PC 명령** | PowerShell 문법을 붙여넣으면 bash `syntax error`. 더 나쁜 건 `ssh`를 또 실행해 **자기 자신에게 재접속**하는 것. 프롬프트를 먼저 볼 것 |
| **PowerShell 파이프로 `authorized_keys` 등록 금지** | PS 5.1이 CRLF/BOM을 섞어 키가 조용히 깨진다. 디바이스 셸에서 `echo '<pubkey>' >> ~/.ssh/authorized_keys` |
| `pkill -f "http.server ..."` | 패턴이 **자기 셸까지 매칭**해 SSH 세션이 끊긴다(exit 255). PID로 kill하거나 bracket 트릭 |

## 7. 개발 환경 (PC · 콘솔)

| 함정 | 요약 |
|---|---|
| **`py -3.14`를 쓸 것** | 아나콘다 `base`엔 `cv2`가 없다. `ModuleNotFoundError: cv2`가 나면 인터프리터를 잘못 잡은 것 |
| **cp949 콘솔 유니코드 크래시** | em-dash(`—`)·`⚠` 등이 Windows 콘솔에서 `UnicodeEncodeError`를 낸다. **파이썬 코드/주석에 쓰지 말 것**(마크다운 문서에는 무관) |
| 카메라 인덱스 변동 | USB 재연결마다 뒤바뀐다. 각 인덱스에서 한 장 캡처해 확인 |
| PC vs 실기 관성 차이 | 관성 지속만 프레임 수 기준이라 PC(29 FPS)에서 2.6배 짧게 보인다 → [`03`](03_algorithm_ptz_tracking.md) §12 |
| 한글 웹폰트 서브셋 | 코드포인트 순으로 쪼개면 효과가 없다(빈도와 무상관). 우선 조각 방식으로 해결됨 → [`issues/2026-07-20_01`](issues/2026-07-20_01_unicode_range_chunking_by_codepoint_is_useless.md) |

## 8. `issues/` 전체 색인

| 파일 | 주제 |
|---|---|
| [`2026-07-11_01`](issues/2026-07-11_01_adb_push_msys_path_mangling.md) | Git Bash adb push 경로 변환 |
| [`2026-07-11_02`](issues/2026-07-11_02_adb_push_directory_nests_when_remote_exists.md) | adb push 디렉토리 중첩 |
| [`2026-07-11_03`](issues/2026-07-11_03_usb_camera_not_detected_via_pd_hub.md) | PD 허브 카메라 미인식 |
| [`2026-07-11_04`](issues/2026-07-11_04_camera_buffer_accumulation_causes_growing_latency.md) | 카메라 버퍼 누적 지연 |
| [`2026-07-16_01`](issues/2026-07-16_01_servo_id_change_takes_effect_immediately.md) | 서보 ID 즉시 반영 |
| [`2026-07-17_01`](issues/2026-07-17_01_homing_offset_wrong_sign_bit_caused_physical_snap.md) | Homing_Offset 부호비트 → 출력물 파손 |
| [`2026-07-19_01`](issues/2026-07-19_01_device_node_names_are_not_stable.md) | 디바이스 노드 번호 불안정 |
| [`2026-07-20_01`](issues/2026-07-20_01_unicode_range_chunking_by_codepoint_is_useless.md) | 한글 폰트 코드포인트 분할 무용 |
| [`2026-07-26_01`](issues/2026-07-26_01_mobile_web_access_fails_random_mac.md) | 폰 랜덤 MAC 접속 실패 |

새 함정을 밟았으면 **한 사건 한 파일**로 `issues/`에 추가하고(증상 → 원인 → 해결 → 재발
방지), 본 문서 §0·§8에 한 줄 추가한다.
