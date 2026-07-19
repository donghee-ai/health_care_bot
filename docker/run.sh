#!/usr/bin/env bash
# run.sh — health_care_bot 컨테이너 빌드 + 실행.
#
# Usage:
#   bash docker/run.sh                  # build (없으면) + run (foreground)
#   bash docker/run.sh --rebuild        # 강제 rebuild + run
#   bash docker/run.sh --shell          # build + bash shell (디버그)
#
# 디바이스 마운트:
#   --device /dev/video0     : USB 카메라
#   --device /dev/ttyUSB0    : ST3215 서보 버스 어댑터 (PTZ 직접 구동)
#   --net host               : HTTP 포트 LAN 노출 (디버그)
#
# 환경:
#   CAMERA_DEV     실제 UVC 카메라 노드. 기본 /dev/video0.
#                  ** 노드 번호는 고정이 아니다 ** - USB 연결 위치/순서와 부팅 시
#                  드라이버 등록 순서에 따라 매 부팅 바뀐다. 2026-07-19 실측에서는
#                  USB 카메라가 video0·1, Venus 코덱이 video2·3이었고, 그 전에는
#                  정반대였다. 실행 전에 반드시 `v4l2-ctl --list-devices`로 확인할 것.
#   CAMERA_INDEX   cv2.VideoCapture에 넘기는 --camera 인자. 기본은 CAMERA_DEV의
#                  숫자를 그대로 씀 (예: CAMERA_DEV=/dev/video2 → 자동으로 2) —
#                  따로 지정하면 그 값 사용.
#   SERIAL_DEV     ST3215 Bus Servo Adapter (USB-serial). 미지정이면 자동 탐색한다.
#                  CH343은 커널/드라이버에 따라 ttyACM 또는 ttyUSB로 잡힌다 —
#                  UNO Q는 CDC-ACM이라 /dev/ttyACM0. 확인은 양쪽 다 볼 것:
#                  `ls /dev/ttyACM* /dev/ttyUSB*`
#                  MCU 경유가 아니라 Linux가 서보 버스를 직접 구동한다.
#   HTTP_PORT      기본 8080
#
# 예: CAMERA_DEV=/dev/video2 bash docker/run.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_NAME="health-care-bot"
IMAGE_TAG="22.04"
IMAGE_FULL="${IMAGE_NAME}:${IMAGE_TAG}"
CONTAINER_NAME="health-care-bot"

CAMERA_DEV="${CAMERA_DEV:-/dev/video0}"
CAMERA_INDEX="${CAMERA_INDEX:-${CAMERA_DEV##*video}}"
# 서보 시리얼 노드 자동 탐색 - 고정 기본값을 두면 노드 이름이 달라졌을 때
# (ttyUSB <-> ttyACM) PTZ가 그대로 disabled로 떨어진다.
if [ -z "${SERIAL_DEV:-}" ]; then
    for _dev in /dev/ttyACM* /dev/ttyUSB*; do
        if [ -e "${_dev}" ]; then SERIAL_DEV="${_dev}"; break; fi
    done
    SERIAL_DEV="${SERIAL_DEV:-/dev/ttyACM0}"
fi
HTTP_PORT="${HTTP_PORT:-8080}"

MODE="${1:-run}"

build_image() {
    local extra=("$@")
    docker build \
        "${extra[@]}" \
        --build-arg USER_UID="$(id -u)" \
        --build-arg USER_GID="$(id -g)" \
        -f "${SCRIPT_DIR}/Dockerfile" \
        -t "${IMAGE_FULL}" \
        "${SCRIPT_DIR}"
}

case "${MODE}" in
    --rebuild)
        echo "==> Force rebuild ${IMAGE_FULL}"
        build_image --no-cache
        MODE="run"
        ;;
    --shell)
        if ! docker image inspect "${IMAGE_FULL}" >/dev/null 2>&1; then
            build_image
        fi
        ;;
    *)
        if ! docker image inspect "${IMAGE_FULL}" >/dev/null 2>&1; then
            echo "==> First build ${IMAGE_FULL}"
            build_image
        else
            echo "==> Reusing cached image ${IMAGE_FULL}"
        fi
        ;;
esac

# 디바이스 인자 — 없으면 패스
DEV_ARGS=()
[ -e "${CAMERA_DEV}" ] && DEV_ARGS+=(--device "${CAMERA_DEV}")
[ -e "${SERIAL_DEV}" ] && DEV_ARGS+=(--device "${SERIAL_DEV}")

if [ "${MODE}" == "--shell" ]; then
    echo "==> Enter shell ${CONTAINER_NAME} (mount: ${PROJECT_ROOT} -> /work)"
    exec docker run --rm -it \
        --name "${CONTAINER_NAME}" \
        --hostname "${CONTAINER_NAME}" \
        --net host \
        "${DEV_ARGS[@]}" \
        -v "${PROJECT_ROOT}:/work" \
        -w /work \
        "${IMAGE_FULL}" \
        bash
fi

echo "==> Run ${CONTAINER_NAME}"
echo "    camera : ${CAMERA_DEV} (--camera ${CAMERA_INDEX}) $([ -e "${CAMERA_DEV}" ] || echo '(MISSING)')"
echo "    serial : ${SERIAL_DEV} $([ -e "${SERIAL_DEV}" ] || echo '(MISSING — PTZ disabled)')"
echo "    http   : http://0.0.0.0:${HTTP_PORT}/"
if [ ! -e "${CAMERA_DEV}" ]; then
    echo
    echo "  !! 카메라 노드 ${CAMERA_DEV} 가 없습니다 - 컨테이너가 즉시 종료됩니다."
    echo "     노드 번호는 부팅마다 바뀝니다. 확인: v4l2-ctl --list-devices"
fi
if [ ! -e "${SERIAL_DEV}" ]; then
    echo
    echo "  !! 서보 시리얼 노드를 찾지 못했습니다 - PTZ 없이(disabled) 실행됩니다."
    echo "     확인: ls /dev/ttyACM* /dev/ttyUSB*   (CH343은 보통 ttyACM0)"
fi
echo

SERIAL_ARG=()
[ -e "${SERIAL_DEV}" ] && SERIAL_ARG=(--serial "${SERIAL_DEV}")

exec docker run --rm -it \
    --name "${CONTAINER_NAME}" \
    --hostname "${CONTAINER_NAME}" \
    --net host \
    "${DEV_ARGS[@]}" \
    -v "${PROJECT_ROOT}:/work" \
    -w /work \
    "${IMAGE_FULL}" \
    python3 /work/src/main.py \
        /work/models/movenet_thunder_int8.tflite \
        --mode auto \
        --camera "${CAMERA_INDEX}" \
        "${SERIAL_ARG[@]}" \
        --serve "${HTTP_PORT}"
