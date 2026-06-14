import io

import soundfile as sf
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from kokoro_onnx import Kokoro
from pydantic import BaseModel

MODEL_PATH = "model/tts/kokoro-v1.0.onnx"
VOICES_PATH = "model/tts/voices-v1.0.bin"

app = FastAPI(title="Vayumi Audio", description="Kokoro TTS API")
kokoro = Kokoro(MODEL_PATH, VOICES_PATH)


class TTSRequest(BaseModel):
    text: str
    voice: str = "af_sarah"
    speed: float = 1.0
    lang: str = "en-us"


@app.get("/")
def root():
    return {"status": "ok", "service": "vayumi-audio"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/voices")
def voices():
    return {"voices": kokoro.get_voices()}


@app.post("/tts")
def tts(req: TTSRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text must not be empty")

    samples, sample_rate = kokoro.create(
        req.text, voice=req.voice, speed=req.speed, lang=req.lang
    )

    buf = io.BytesIO()
    sf.write(buf, samples, sample_rate, format="WAV")
    buf.seek(0)
    return StreamingResponse(buf, media_type="audio/wav")
