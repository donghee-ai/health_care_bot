# 2026-07-19 — PTZ 관성 추적 시점 스냅샷

`src/ptz_controller.py` 백업. git 커밋 `9eeee60` (태그 `v3`)과 동일한 내용.

## 이 시점에 담긴 것

- **시간 기준 제어** — 추적 속도가 deg/s로 표현돼 프레임레이트와 무관
  (`gain_deg_per_s=232`, `max_deg_per_s=116`)
- **명령 쿨다운 80ms** — 서보(50 deg/s)가 목표보다 빨라 먼저 도착해 멈추던
  문제 해소 (기존 250ms)
- **추적 손실 관성 복구 사다리** (yaw 전용)
  관성 -> 1초 대기 -> 관성 이전 복귀 -> 2초 대기 -> 중앙 복귀.
  어느 단계든 재검출되면 즉시 취소.
- **관성 속도 = 카메라 각속도 + 화면 내 피사체 이동량 x 화각**
  둘 중 하나만 보면 놓치는 경우가 있어 합으로 낸다. 상세는
  `docs/history/2026-07-19_02`.

## 튜닝값

| 필드 | 값 |
|---|---|
| `coast_start_misses` | 3 |
| `coast_frames` | 15 (11 FPS에서 1.36초) |
| `coast_decay` | 0.9 (약 44도 이동) |
| `coast_fov_deg` | 60 (**추정값 — 실측 보정 필요**) |

## 주의

**실기 체감 확인이 안 된 상태다.** 시뮬레이션 검증만 통과했다. 다음 세션에서
실기 확인 후 `coast_decay` / `coast_fov_deg`를 조정할 가능성이 높다.

## 되돌리기

```powershell
Copy-Item backup\2026-07-19_ptz_inertia_tracking\ptz_controller.py src\ptz_controller.py
```

git이 있으므로 아래도 동일하다:

```powershell
git checkout v3 -- src/ptz_controller.py
```
