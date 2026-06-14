import asyncio
import io
import os
import re
from functools import lru_cache

import numpy as np
import soundfile as sf
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from kokoro_onnx import Kokoro
from pydantic import BaseModel

MODEL_PATH = "model/tts/kokoro-v1.0.onnx"
VOICES_PATH = "model/tts/voices-v1.0.bin"
SAMPLE_RATE = 24000
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

app = FastAPI(title="Vayumi Audio", description="Kokoro TTS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Loaded once at process startup, reused for every request.
kokoro = Kokoro(MODEL_PATH, VOICES_PATH)

# One ONNX inference at a time — concurrent calls compete for CPU and raise latency.
_synth_sem = asyncio.Semaphore(1)

_STREAM_HEADERS = {
    "X-Sample-Rate": str(SAMPLE_RATE),
    "X-Sample-Format": "s16le",
    "X-Channels": "1",
    "X-Accel-Buffering": "no",
    "Cache-Control": "no-cache, no-store",
}

_SENTENCE_RE = re.compile(r"(?<=[.!?…])\s+")


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_RE.split(text.strip())
    return [p.strip() for p in parts if p.strip()] or [text.strip()]


class TTSRequest(BaseModel):
    text: str
    voice: str = "af_heart"
    speed: float = 1.0
    lang: str = "en-us"


@app.get("/")
def dashboard():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": True}


@app.get("/voices")
def voices():
    return {"voices": kokoro.get_voices()}


@lru_cache(maxsize=64)
def _synthesize_wav(text: str, voice: str, speed: float, lang: str) -> bytes:
    samples, sample_rate = kokoro.create(text, voice=voice, speed=speed, lang=lang)
    buf = io.BytesIO()
    sf.write(buf, samples, sample_rate, format="WAV")
    return buf.getvalue()


@app.post("/tts")
def tts(req: TTSRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text must not be empty")

    wav_bytes = _synthesize_wav(req.text, req.voice, req.speed, req.lang)
    return StreamingResponse(io.BytesIO(wav_bytes), media_type="audio/wav")


@app.post("/tts/stream")
async def tts_stream(req: TTSRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text must not be empty")

    async def generate():
        sentences = _split_sentences(req.text)
        async with _synth_sem:
            for sentence in sentences:
                async for samples, _ in kokoro.create_stream(
                    sentence,
                    voice=req.voice,
                    speed=req.speed,
                    lang=req.lang,
                ):
                    pcm16 = (samples * 32767).astype(np.int16).tobytes()
                    yield pcm16
                    # Yield to the event loop so uvicorn flushes bytes immediately.
                    await asyncio.sleep(0)

    return StreamingResponse(
        generate(),
        media_type="application/octet-stream",
        headers=_STREAM_HEADERS,
    )
