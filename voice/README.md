# Voice mode (Stage 8 — stretch goal)

This is a stretch goal, not part of the core hackathon submission. The web UI at `localhost:3000` is the primary deliverable.

That said: the voice gateway here demonstrates that **the same backend powers a voice-first assessment with no backend changes**. Each candidate utterance becomes a `POST /api/assess/respond`; the next question becomes ElevenLabs TTS audio. The "agent brain" never moves — only the input/output modality changes.

## Architecture

```
Daily.co WebRTC room (or Twilio phone)
    │
    ▼
Pipecat pipeline:
  transport.input()      ← microphone audio
    → Deepgram STT       ← nova-3, real-time
    → AssessmentBridge   ← POST /api/assess/respond
    → ElevenLabs TTS     ← turbo v2.5
    → transport.output() ← speaker audio
    │
    ▼
FastAPI backend (unchanged)
```

The same `/start` opens the session and gets the first question; the same `/respond` is invoked once per spoken candidate turn. When the backend signals `interview_complete=true`, the bridge fetches `/result/{session_id}` and reads the candidate-facing summary aloud as the closing.

## Setup

```bash
# From the repo root
pip install -r voice/requirements.txt
```

Required env vars:
```bash
DEEPGRAM_API_KEY=...
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM   # optional; default is Rachel
BACKEND_URL=http://localhost:8000           # where the FastAPI backend is reachable
```

For browser/WebRTC usage (recommended for the demo):
```bash
DAILY_ROOM_URL=https://your-domain.daily.co/room-name
DAILY_TOKEN=...
```

For phone-based usage, swap the `DailyTransport` in `gateway.py` for Pipecat's [Twilio WebSocket transport](https://docs.pipecat.ai/server/services/transport/twilio-websocket-server) and add:
```bash
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...
```

## Run

With the FastAPI backend already running at `localhost:8000`:

```bash
python -m voice.gateway \
    --resume samples/01_senior_ai_engineer_resume.txt \
    --jd samples/01_senior_ai_engineer_jd.txt \
    --room-url $DAILY_ROOM_URL \
    --token $DAILY_TOKEN
```

Then join the same Daily room from a browser. The bot will:
1. Greet you
2. Speak the first question (e.g., "Here's the first question on Python at level 3 — Apply...")
3. Wait for your spoken answer
4. POST it to `/api/assess/respond`
5. Speak the next question
6. ...repeat until the interview completes
7. Read the candidate summary aloud
8. End the call

## Why this proves something

The whole architecture point of having the IRT loop, scoring, gap analysis, and learning plan all live in the FastAPI backend (and not in the frontend) is exactly so adding voice mode is a thin adapter, not a rewrite. The web UI and the voice gateway are peers — both clients of the same agent. That's the [Anthropic "Building Effective Agents"](https://www.anthropic.com/research/building-effective-agents) Orchestrator-Workers pattern paying off.

## Status

Code is complete and wired correctly against Pipecat's published APIs as of April 2026. **Not exercised in CI** — running it requires real Deepgram + ElevenLabs + Daily/Twilio credentials. If you want to demo this live, plan to spend ~30 minutes setting up accounts and one tweak run before recording.
