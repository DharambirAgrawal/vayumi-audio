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

MODEL_PATH = os.getenv("KOKORO_MODEL", "model/tts/kokoro-v1.0.int8.onnx")
VOICES_PATH = os.getenv("KOKORO_VOICES", "model/tts/voices-v1.0.bin")
SAMPLE_RATE = 24000
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
MAX_CHUNK_CHARS = 100

app = FastAPI(title="Vayumi Audio", description="Kokoro TTS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

kokoro = Kokoro(MODEL_PATH, VOICES_PATH)

_synth_sem = asyncio.Semaphore(1)

_STREAM_HEADERS = {
    "X-Sample-Rate": str(SAMPLE_RATE),
    "X-Sample-Format": "s16le",
    "X-Channels": "1",
    "X-Accel-Buffering": "no",
    "Cache-Control": "no-cache, no-store",
}

_CLAUSE_RE = re.compile(r"(?<=[,;:—–])\s+|(?<=[.!?…])\s+")


def _split_chunks(text: str) -> list[str]:
    """Split text into small clauses so the first audio arrives quickly."""
    parts = _CLAUSE_RE.split(text.strip())
    chunks: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        while len(part) > MAX_CHUNK_CHARS:
            split_at = part.rfind(" ", 0, MAX_CHUNK_CHARS)
            if split_at <= 0:
                split_at = MAX_CHUNK_CHARS
            chunks.append(part[:split_at].strip())
            part = part[split_at:].strip()
        if part:
            chunks.append(part)
    return chunks or [text.strip()]


def _to_pcm16(samples: np.ndarray) -> bytes:
    return (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16).tobytes()


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
    return {
        "status": "ok",
        "model_loaded": True,
        "model": os.path.basename(MODEL_PATH),
    }


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

    chunks = _split_chunks(req.text)

    async def generate():
        queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=4)

        async def produce():
            async with _synth_sem:
                for chunk_text in chunks:
                    async for samples, _ in kokoro.create_stream(
                        chunk_text,
                        voice=req.voice,
                        speed=req.speed,
                        lang=req.lang,
                    ):
                        await queue.put(_to_pcm16(samples))
            await queue.put(None)

        producer = asyncio.create_task(produce())
        try:
            while True:
                pcm = await queue.get()
                if pcm is None:
                    break
                yield pcm
                await asyncio.sleep(0)
        finally:
            await producer

    return StreamingResponse(
        generate(),
        media_type="application/octet-stream",
        headers=_STREAM_HEADERS,
    )
