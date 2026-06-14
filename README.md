---
title: Vayumi Audio
emoji: 🔊
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# Vayumi Audio

Text-to-speech microservice for the Vayumi project, powered by [Kokoro](https://github.com/thewh1teagle/kokoro-onnx) via ONNX Runtime.

## API

- `GET /health` — health check
- `GET /voices` — list available voices
- `POST /tts` — generate speech audio (WAV)

  ```json
  {
    "text": "Hello world",
    "voice": "af_sarah",
    "speed": 1.0,
    "lang": "en-us"
  }
  ```
