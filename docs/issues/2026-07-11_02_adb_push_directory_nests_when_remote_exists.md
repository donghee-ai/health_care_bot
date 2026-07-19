# `adb push <local_dir> <remote_dir>`가 remote_dir이 이미 있으면 안에 중첩됨

## 증상

`web/dist`를 두 번째로 다시 push했는데 `6 files pushed` 성공 메시지가 떴지만,
디바이스의 `/home/arduino/health_care_bot/web/dist/assets/`에는 여전히 첫
push 때의 구버전 해시 파일(`index-C9fJj-zX.js` 등)만 있고 최신 빌드가
반영되지 않음.

## 원인

`adb push <local_dir> <remote_dir>`는 `remote_dir`이 **이미 존재하는
디렉토리**면 `local_dir`의 내용을 `remote_dir` 안에 바로 풀어놓는 게 아니라
`remote_dir/<local_dir 이름>/` 형태로 통째로 복사한다. 즉 이미
`/home/arduino/health_care_bot/web/dist`가 존재하는 상태에서
`adb push web/dist .../web/dist`를 다시 실행하면 실제로는
`.../web/dist/dist/`가 새로 생기고, 원래 있던 `.../web/dist/`는 그대로
구버전으로 남는다. `http_server.py`가 서빙하는 경로는 항상
`.../web/dist/`이므로 새 파일이 반영 안 된 것처럼 보임.

## 해결

```powershell
& $ADB shell "rm -rf /home/arduino/health_care_bot/web/dist"
& $ADB push web/dist /home/arduino/health_care_bot/web/dist
```

remote 경로를 먼저 지워서 "존재하지 않는 상태"로 만든 뒤 push하면 내용이
바로 그 경로에 풀린다.

## 재발 방지

- `web/dist`처럼 **매번 새 해시 파일명이 나오는 빌드 산출물 디렉토리**를
  다시 push할 땐 항상 `rm -rf <remote_dir>` 먼저 실행 후 push한다.
- push 후에는 성공 로그를 믿지 말고 `ls -la <remote_dir>/assets/`로 파일명
  해시가 로컬 최신 빌드와 일치하는지 직접 확인한다
  (`web/ARCHITECTURE.md`에는 없는, 순수 배포 절차 함정 — 관련:
  [`2026-07-11_01_adb_push_msys_path_mangling.md`](2026-07-11_01_adb_push_msys_path_mangling.md)).
