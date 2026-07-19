# health_care_bot — 단일 컨테이너 (squat + pushup + ptz)
# 기반: 기존 unoq-companion-robot/pose/docker/Dockerfile.pose 와 호환 (디바이스 venv-unoq 일치).
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# python3.10 / opencv / serial 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.10 \
        python3-pip \
        python3.10-venv \
        libgl1-mesa-glx \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Non-root user — host UID/GID 와 일치 (mount 권한 / dialout 그룹)
ARG USER_NAME=dev
ARG USER_UID=1000
ARG USER_GID=1000
RUN groupadd -g ${USER_GID} ${USER_NAME} && \
    useradd -m -u ${USER_UID} -g ${USER_GID} -G dialout,video -s /bin/bash ${USER_NAME}

WORKDIR /tmp
COPY requirements.txt /tmp/
RUN python3 -m pip install --upgrade pip setuptools wheel && \
    python3 -m pip install -r /tmp/requirements.txt && \
    rm -f /tmp/requirements.txt

USER ${USER_NAME}
WORKDIR /work

EXPOSE 8080
CMD ["python3", "/work/src/main.py", \
     "/work/models/movenet_thunder_int8.tflite", \
     "--mode", "auto", \
     "--camera", "0", \
     "--serial", "/dev/ttyACM0", \
     "--serve", "8080"]
