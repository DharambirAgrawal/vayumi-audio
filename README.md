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

## Dashboard

`GET /` serves a small built-in dashboard to test voices, generation, and streaming directly in the browser.

## API

- `GET /health` — health check, includes `model_loaded` (model is loaded once at process startup, not per request)
- `GET /voices` — list available voices
- `POST /tts` — generate speech audio (WAV, full file, response cached for repeated identical requests)

  ```json
  {
    "text": "Hello world",
    "voice": "af_heart",
    "speed": 1.0,
    "lang": "en-us"
  }
  ```

- `POST /tts/stream` — same request body, streams raw PCM16LE audio chunks as they're generated for low-latency playback. Response headers:
  - `X-Sample-Rate: 24000`
  - `X-Sample-Format: s16le`
  - `X-Channels: 1`
