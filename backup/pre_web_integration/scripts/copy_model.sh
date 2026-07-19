#!/usr/bin/env bash
# copy_model.sh — 기존 pose 라인 자산을 본 라인 models/ 로 복사.
#
# 본 라인은 자체 모델을 포함하지 않음 (용량/라이센스). 실행 전 한 번만 호출.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

SRC="${PROJECT_ROOT}/../unoq-companion-robot/pose/models/movenet_thunder_int8.tflite"
DST_DIR="${PROJECT_ROOT}/models"
DST="${DST_DIR}/movenet_thunder_int8.tflite"

if [ ! -f "${SRC}" ]; then
    echo "ERROR: source model not found: ${SRC}"
    echo "       기존 pose 라인 (../unoq-companion-robot/pose/) 의 모델이 필요합니다."
    exit 1
fi

mkdir -p "${DST_DIR}"
cp -v "${SRC}" "${DST}"

# 크기 sanity (6~7 MB 예상)
SIZE=$(stat -c '%s' "${DST}" 2>/dev/null || stat -f '%z' "${DST}")
echo "Copied ${SIZE} bytes → ${DST}"
if [ "${SIZE}" -lt 5000000 ] || [ "${SIZE}" -gt 9000000 ]; then
    echo "WARN: 예상 크기 (6~7 MB) 와 다름 — 모델 손상 확인 필요"
fi
