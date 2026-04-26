"""
TTS proxy endpoint — streams ElevenLabs audio to the frontend.

Returns 204 if no ELEVENLABS_API_KEY → frontend uses browser SpeechSynthesis.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel
import httpx

from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech"


class TTSRequest(BaseModel):
    text: str
    voice_id: str | None = None


@router.post("/tts")
async def text_to_speech(req: TTSRequest):
    """
    Convert text to speech via ElevenLabs.
    Returns 204 (no content) if ElevenLabs is not configured — frontend
    detects this and falls back to browser SpeechSynthesis.
    """
    api_key = getattr(settings, "elevenlabs_api_key", None)
    if not api_key:
        return Response(status_code=204)

    voice_id = req.voice_id or getattr(settings, "elevenlabs_voice_id", "21m00Tcm4TlvDq8ikWAM")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                f"{ELEVENLABS_URL}/{voice_id}",
                headers={
                    "xi-api-key": api_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                json={
                    "text": req.text,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {
                        "stability": 0.35,        # lower = more expressive, natural variation
                        "similarity_boost": 0.80,  # stay close to voice character
                        "style": 0.45,             # add emotional warmth / expressiveness
                        "use_speaker_boost": True,
                    },
                },
            )
            r.raise_for_status()
            return Response(
                content=r.content,
                media_type="audio/mpeg",
                headers={"Cache-Control": "no-cache"},
            )
    except Exception as e:
        # Any failure → 204 so frontend falls back to browser TTS
        # Don't return 502 — it clutters logs and the frontend handles 204 gracefully
        logger.warning(f"ElevenLabs TTS failed, falling back to browser: {e}")
        return Response(status_code=204)