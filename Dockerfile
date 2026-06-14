FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    espeak-ng \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p model/tts && \
    wget -q -O model/tts/kokoro-v1.0.int8.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx && \
    wget -q -O model/tts/voices-v1.0.bin https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin

ENV KOKORO_MODEL=model/tts/kokoro-v1.0.int8.onnx
ENV KOKORO_VOICES=model/tts/voices-v1.0.bin

COPY app/ app/

EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
