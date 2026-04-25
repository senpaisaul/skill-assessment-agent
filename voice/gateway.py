"""
Voice gateway — Pipecat-based skill assessment over voice.

THIS IS A STAGE 8 STRETCH GOAL. It is NOT required for the hackathon submission;
the core deliverable runs entirely through the web UI. This module exists to
demonstrate that the same backend powers a voice-first assessment with no
backend changes.

ARCHITECTURE:
    Twilio (phone) ↔ Pipecat pipeline ↔ existing FastAPI backend
                             │
                             ├─ Deepgram STT (nova-3)
                             ├─ Custom processor: maps speech turns to
                             │  POST /api/assess/start and /respond
                             └─ ElevenLabs TTS (turbo v2.5)

THE TRICK:
The web UI sends questions one at a time via JSON. The voice flow needs
exactly the same shape: the bot speaks the question, the candidate speaks
back, we POST that to /respond, get the next question, speak it, repeat.

So the entire "agent brain" stays in the FastAPI backend. The voice gateway
is a thin adapter that translates between speech turns and JSON API calls.

REQUIREMENTS:
- pip install pipecat-ai[deepgram,elevenlabs,silero,twilio]
- DEEPGRAM_API_KEY, ELEVENLABS_API_KEY in env
- For phone: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN + a Twilio number
- For browser/WebRTC: just run this and hit a Pipecat client SDK

RUN:
    python -m voice.gateway --resume path/to/resume.txt --jd path/to/jd.txt
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Optional

import httpx

# Pipecat imports are guarded — this module imports cleanly even if
# pipecat-ai isn't installed, so the README's "Stage 8 is optional" promise
# holds. The check fires at runtime if you actually try to start the gateway.
try:
    from pipecat.frames.frames import (
        EndFrame,
        LLMMessagesFrame,
        TextFrame,
        TranscriptionFrame,
    )
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineParams, PipelineTask
    from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
    from pipecat.services.deepgram.stt import DeepgramSTTService
    from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
    from pipecat.transports.network.daily import DailyParams, DailyTransport
    PIPECAT_AVAILABLE = True
except ImportError:
    PIPECAT_AVAILABLE = False


BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")


# ---------------------------------------------------------------------------
# Backend client — thin async wrapper around the FastAPI endpoints
# ---------------------------------------------------------------------------

class AssessmentClient:
    """Async client for the existing /start and /respond API."""

    def __init__(self, base_url: str = BACKEND_URL):
        self.base_url = base_url.rstrip("/")
        self.session_id: Optional[str] = None

    async def start(self, resume_text: str, jd_text: str) -> dict:
        """Returns the first question payload (or None if no questions needed)."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                f"{self.base_url}/api/assess/start",
                json={"resume_text": resume_text, "jd_text": jd_text},
            )
            r.raise_for_status()
            data = r.json()
        self.session_id = data["session_id"]
        return data

    async def respond(self, response_text: str) -> dict:
        """Submit candidate's spoken answer; returns next-question payload or completion."""
        if not self.session_id:
            raise RuntimeError("respond() called before start()")
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                f"{self.base_url}/api/assess/respond",
                json={"session_id": self.session_id, "response": response_text},
            )
            r.raise_for_status()
            return r.json()

    async def result(self) -> dict:
        """Final assessment + plan."""
        if not self.session_id:
            raise RuntimeError("result() called before start()")
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.get(f"{self.base_url}/api/assess/result/{self.session_id}")
            r.raise_for_status()
            return r.json()


# ---------------------------------------------------------------------------
# Pipecat processor — bridges speech turns to backend JSON calls
# ---------------------------------------------------------------------------

if PIPECAT_AVAILABLE:

    class AssessmentBridge(FrameProcessor):
        """
        Sits between STT (input) and TTS (output) in the pipeline.

        - Receives TranscriptionFrame from Deepgram
        - POSTs to /api/assess/respond
        - Emits a TextFrame with the next question, which TTS speaks aloud
        - On completion, emits a closing summary text and then EndFrame
        """

        def __init__(self, client: AssessmentClient):
            super().__init__()
            self.client = client
            self.first_question: Optional[str] = None
            self.completed = False

        async def speak_first_question(self, question: str) -> None:
            """Called by the runner once after the pipeline starts — opens with the first question."""
            self.first_question = question
            opening = (
                "Hi! I'm going to ask you a few questions to assess your skills "
                "for this role. Please answer each one as fully as you can. "
                f"Here's the first question. {question}"
            )
            await self.push_frame(TextFrame(opening))

        async def process_frame(self, frame, direction: FrameDirection):
            await super().process_frame(frame, direction)

            # Only react to incoming transcriptions
            if not isinstance(frame, TranscriptionFrame):
                await self.push_frame(frame, direction)
                return

            if self.completed:
                return

            # Skip empty / whitespace-only transcriptions (Deepgram emits these on pause)
            if not frame.text or not frame.text.strip():
                return

            # POST the candidate's spoken response and get the next question
            try:
                resp = await self.client.respond(frame.text.strip())
            except Exception as e:
                await self.push_frame(TextFrame(
                    f"I'm having trouble reaching the assessment service. "
                    f"Let's pause here. Error: {e}"
                ))
                await self.push_frame(EndFrame())
                self.completed = True
                return

            if resp.get("interview_complete"):
                # Fetch the final summary and speak it
                self.completed = True
                try:
                    result = await self.client.result()
                    summary = (result.get("gap_analysis") or {}).get("summary") \
                        or "Assessment complete. Detailed results are available on the web."
                    plan_summary = (result.get("learning_plan") or {}).get("summary") or ""
                    closing = (
                        "That's all the questions. Here's where you stand. "
                        f"{summary} "
                        f"{plan_summary} "
                        "Detailed results, with evidence quotes and curated learning resources, "
                        "are now available on the web. Thanks for the conversation."
                    )
                    await self.push_frame(TextFrame(closing))
                except Exception:
                    await self.push_frame(TextFrame(
                        "Assessment complete. Detailed results are available on the web. "
                        "Thanks for the conversation."
                    ))
                await self.push_frame(EndFrame())
                return

            # Speak the next question
            next_q = resp.get("next_question") or {}
            question = next_q.get("question")
            skill = next_q.get("skill")
            if question:
                preface = f"Next question, on {skill}. " if skill else "Next question. "
                await self.push_frame(TextFrame(preface + question))


    async def run_voice_assessment(resume_text: str, jd_text: str, room_url: str, token: str) -> None:
        """
        Run a voice-mode assessment over a Daily.co WebRTC room.

        For Twilio phone-based use, swap DailyTransport for the Pipecat Twilio
        transport (https://docs.pipecat.ai/server/services/transport/twilio-websocket-server).
        """
        # 1) Start the backend session — we need the first question before audio starts
        client = AssessmentClient()
        start_payload = await client.start(resume_text, jd_text)
        first_q = (start_payload.get("next_question") or {}).get("question")
        if not first_q:
            print("Backend returned no first question (graph completed without interview).")
            return

        # 2) Wire up the Pipecat pipeline
        transport = DailyTransport(
            room_url=room_url,
            token=token,
            bot_name="Skill Assessment",
            params=DailyParams(audio_in_enabled=True, audio_out_enabled=True),
        )
        stt = DeepgramSTTService(api_key=os.environ["DEEPGRAM_API_KEY"])
        tts = ElevenLabsTTSService(
            api_key=os.environ["ELEVENLABS_API_KEY"],
            voice_id=os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM"),  # default voice
            model="eleven_turbo_v2_5",
        )
        bridge = AssessmentBridge(client)

        pipeline = Pipeline([
            transport.input(),
            stt,
            bridge,
            tts,
            transport.output(),
        ])

        task = PipelineTask(pipeline, params=PipelineParams(allow_interruptions=True))

        # Speak the opening + first question once the bot is in the room
        @transport.event_handler("on_first_participant_joined")
        async def _on_join(transport, participant):
            await bridge.speak_first_question(first_q)

        runner = PipelineRunner()
        await runner.run(task)


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def _read_text(path: Optional[str]) -> str:
    if not path:
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main() -> int:
    if not PIPECAT_AVAILABLE:
        print(
            "voice.gateway requires pipecat-ai. Install with:\n"
            "  pip install 'pipecat-ai[deepgram,elevenlabs,silero,daily]'\n",
            file=sys.stderr,
        )
        return 1

    parser = argparse.ArgumentParser(description="Voice-mode skill assessment")
    parser.add_argument("--resume", required=True, help="Path to resume text file")
    parser.add_argument("--jd", required=True, help="Path to JD text file")
    parser.add_argument(
        "--room-url",
        default=os.environ.get("DAILY_ROOM_URL"),
        help="Daily.co room URL (or set DAILY_ROOM_URL)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("DAILY_TOKEN"),
        help="Daily.co meeting token (or set DAILY_TOKEN)",
    )
    args = parser.parse_args()

    if not args.room_url or not args.token:
        print("Daily room URL and token are required (--room-url/--token or env).", file=sys.stderr)
        return 1
    for var in ("DEEPGRAM_API_KEY", "ELEVENLABS_API_KEY"):
        if not os.environ.get(var):
            print(f"Missing env var: {var}", file=sys.stderr)
            return 1

    resume_text = _read_text(args.resume)
    jd_text = _read_text(args.jd)
    if not resume_text.strip() or not jd_text.strip():
        print("Resume and JD files must be non-empty.", file=sys.stderr)
        return 1

    asyncio.run(run_voice_assessment(resume_text, jd_text, args.room_url, args.token))
    return 0


if __name__ == "__main__":
    sys.exit(main())
