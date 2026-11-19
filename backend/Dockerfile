# CPU image by default; docker-compose.gpu.yml swaps in the CUDA runtime so
# faster-whisper and h264_nvenc can use an NVIDIA GPU.
ARG BASE_IMAGE=ubuntu:24.04
FROM ${BASE_IMAGE}
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-venv python3-pip ffmpeg fonts-inter fonts-dejavu-core curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN python3 -m venv /venv
ENV PATH=/venv/bin:$PATH
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# YuNet face model; if unreachable the reframer falls back to OpenCV's bundled Haar cascade.
RUN mkdir -p /models && (curl -fsSL -o /models/face_detection_yunet_2023mar.onnx \
      https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx \
    || (rm -f /models/*.onnx && echo "YuNet download failed; using Haar fallback"))
COPY app ./app
