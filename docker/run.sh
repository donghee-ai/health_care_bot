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
#   CAMERA_DEV     기본 /dev/video0 — 실제 UVC 카메라 노드로 바꿔서 지정
#                  (Qualcomm Venus 코덱이 /dev/video0·1을 먼저 차지하는 보드에서는
#                  보통 /dev/video2 이상이 진짜 카메라. `v4l2-ctl --list-devices`로 확인)
#   CAMERA_INDEX   cv2.VideoCapture에 넘기는 --camera 인자. 기본은 CAMERA_DEV의
#                  숫자를 그대로 씀 (예: CAMERA_DEV=/dev/video2 → 자동으로 2) —
#                  따로 지정하면 그 값 사용.
#   SERIAL_DEV     기본 /dev/ttyUSB0 — ST3215 Bus Servo Adapter (USB-serial).
#                  MCU 경유가 아니라 Linux가 서보 버스를 직접 구동한다.
#                  (`ls /dev/ttyUSB*` 로 확인. CH343/CP210x 등으로 잡힘)
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
SERIAL_DEV="${SERIAL_DEV:-/dev/ttyUSB0}"
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
