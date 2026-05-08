<img width="18709" height="4678" alt="hero" src="https://github.com/user-attachments/assets/016241d8-8b57-44fd-9cd3-02f0cc451b28" />



<h1 align="center">
  SARVAM <code>x</code> LIVEKIT
</h1>

<p align="center">
  <strong>Real-Time Voice Agent</strong>
</p>

<p align="center">
  <code>speech -> intelligence -> voice</code>
</p>

---

Minimal real-time voice AI agent built with **LiveKit**, **Sarvam**, and **OpenAI**.

## What It Does

- Listens through LiveKit WebRTC
- Transcribes speech with Sarvam STT
- Generates replies with OpenAI
- Speaks back with Sarvam Bulbul TTS
- Uses STT-based turn detection
- Logs transcripts, metrics, state changes, and errors

## Files

```text
.
+-- agent.py
+-- requirements.txt
+-- ARCHITECTURE_AUDIT.md
+-- assets/
|   +-- logo.png
+-- .env
```

## Setup

```powershell
pip install -r requirements.txt
```

Create `.env`:

```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_key
LIVEKIT_API_SECRET=your_livekit_secret
SARVAM_API_KEY=your_sarvam_key
OPENAI_API_KEY=your_openai_key
```

Optional:

```env
SARVAM_STT_LANGUAGE=unknown
SARVAM_STT_MODEL=saaras:v3
SARVAM_TTS_LANGUAGE=en-IN
SARVAM_TTS_MODEL=bulbul:v3
SARVAM_TTS_SPEAKER=shubh
OPENAI_PRIMARY_LLM=gpt-4o
OPENAI_FALLBACK_LLM=gpt-4o-mini
LOG_LEVEL=INFO
```

## Run Locally

Start the agent:

```powershell
python agent.py dev
```

Test from console:

```powershell
python agent.py console
```

## Deploy

On your server:

```powershell
pip install -r requirements.txt
python agent.py start
```

Set secrets in your hosting platform. Do not commit `.env`.

## Notes

- Sarvam handles voice activity and turn detection.
- `AgentSession` should not receive a separate VAD.
- Full technical audit: `ARCHITECTURE_AUDIT.md`

## License

MIT
