# Git Bash에서 `adb push`가 "성공" 메시지를 내고도 실제로는 파일을 안 옮김

## 증상

Git Bash(Bash 도구)에서 `adb push src/app_state.py /home/arduino/health_care_bot/src/app_state.py`
실행 시 `1 file pushed, 0 skipped ...` 성공 로그가 찍히지만, 바로 이어서
`adb: error: failed to copy '...' to 'C:/Program Files/Git/home/arduino/...':
remote secure_mkdirs failed: No such file or directory`도 함께 출력됨.
디바이스에서 `md5sum`/`wc -l`로 확인해보면 파일이 실제로 갱신되지 않았음
(구버전 그대로).

## 원인

`adb.exe`는 MSYS 빌드가 아닌 네이티브 Win32 실행파일인데, Git Bash(MSYS2)는
`/`로 시작하는 인자를 native 실행파일에 넘길 때 자동으로 Windows 경로로
변환한다. `adb push`의 두 번째 인자(디바이스 쪽 리모트 경로,
`/home/arduino/...`)가 `C:/Program Files/Git/home/arduino/...`로 잘못
변환되어 adb에 전달됨 — adb는 이걸 그대로 리모트 경로 문자열로 보내고,
디바이스(Linux)에서 그런 이름의 디렉토리를 만들려다 실패한 것.

## 해결

같은 명령을 PowerShell 도구로 재실행하면 경로 변환이 일어나지 않아 정상
동작. `md5sum`으로 디바이스 파일 해시를 재확인해 실제 반영 검증.

## 재발 방지

- **디바이스(리모트) 경로를 인자로 받는 adb 명령(`push`/`pull`/`shell`에
  절대경로 전달 등)은 Bash(Git Bash) 대신 PowerShell 도구를 사용한다.**
- Bash를 꼭 써야 하면 `MSYS_NO_PATHCONV=1` 환경변수로 우회 가능하다고
  알려져 있으나 이번엔 검증하지 않음 — PowerShell 사용이 확실한 방법.
- adb push 성공 로그만 보고 반영을 확신하지 말고, 중요한 파일은 push 후
  `md5sum`/`wc -l` 등으로 디바이스 쪽을 직접 재확인한다.
