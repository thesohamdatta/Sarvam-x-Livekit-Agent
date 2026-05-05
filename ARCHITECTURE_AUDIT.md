# Voice AI Architecture Audit

## 1. Ground Truth From The Transcription

The workshop material defines a LiveKit real-time voice agent:

- Pipeline: LiveKit room audio -> Sarvam STT -> OpenAI LLM -> Sarvam Bulbul TTS -> LiveKit audio output.
- Transport: LiveKit/WebRTC for real-time audio, giving UDP-first media behavior rather than request/response audio uploads over TCP.
- Latency target: optimize for a sub-500 ms conversational feel; the Sarvam STT section specifically calls out about 70 ms processing latency.
- Turn-taking: Sarvam should own speech start/end detection. Do not pass a separate VAD to `AgentSession`.
- Required STT config: `flush_signal=True`.
- Required session config: `turn_detection="stt"` and `min_endpointing_delay=0.07`.
- Language behavior: `language="unknown"` for auto-detection and multilingual/code-mixed speech.
- Personality: friendly, concise, conversational, and voice-native.
- Reliability: production agents need fallback paths for provider failures.
- Metrics: track STT/LLM/TTS timings, token usage, interruptions, and transcripts.
- Observability: logs, traces/metrics, final transcripts, and failure visibility.
- Deployment: cloud-compatible worker process configured by environment variables.
- Tooling: tools/MCP/function calls are supported by the framework, but the transcription does not specify a concrete domain tool.

## 2. Intended Architecture

```text
User microphone
  -> LiveKit WebRTC room
  -> AgentSession audio input
  -> Sarvam streaming STT with flush_signal=true
  -> STT-owned end-of-turn detection
  -> OpenAI streaming LLM
  -> Sarvam streaming TTS
  -> LiveKit WebRTC audio playout
```

Parallelization points:

- Audio ingestion and streaming STT happen while the user is still speaking.
- LLM starts immediately after STT endpointing.
- TTS streams as response text becomes available.
- Metrics and transcript logging are side effects and must not block the audio path.

Failure handling:

- LLM falls back to a smaller OpenAI model on timeout/connection failure.
- TTS falls back to OpenAI TTS if Sarvam TTS fails.
- STT remains Sarvam-first because replacing it can break the workshop's STT-owned turn detection model.

## 3. Existing Project Audit

The local project directory was empty before reconstruction. There was no implementation to compare beyond absence.

Findings:

- Missing voice pipeline.
- Missing `.env` and dependency manifest.
- Missing Sarvam turn-taking best practices.
- Missing observability for metrics, transcripts, states, and errors.
- Missing fallback strategy.
- Missing architecture documentation.

SDK compatibility finding:

- Installed `livekit-agents==1.3.11` exposes `sarvam.STT(..., flush_signal=...)`, but not the transcription's `mode="transcribe"` / `mode="translate"` argument.
- Installed Sarvam plugin type hints list older model names, while the workshop uses `saaras:v3` and `bulbul:v3`. The rebuilt agent keeps those values environment-driven, but they must be runtime-validated against Sarvam and the installed plugin.

## 4. Evaluation

| Area | Before | After Reconstruction |
| --- | --- | --- |
| Architecture correctness | Absent | LiveKit -> Sarvam STT -> OpenAI LLM -> Sarvam TTS |
| Latency | Absent | Streaming transport, STT turn detection, 70 ms endpointing |
| Naturalness | Absent | Concise voice prompt, interruptions, false interruption resume |
| Reliability | Absent | LLM and TTS fallback adapters |
| Observability | Absent | Metrics, transcripts, state changes, errors |
| Deployment readiness | Folder only | Runnable LiveKit worker with env config |

## 5. Improvements Implemented

- Added `.env` with required provider configuration.
- Added `requirements.txt`.
- Added `.gitignore` to prevent committing secrets.
- Added `agent.py` with:
  - `turn_detection="stt"`
  - `min_endpointing_delay=0.07`
  - no explicit VAD in `AgentSession`
  - `flush_signal=True` on Sarvam STT
  - interruptions enabled
  - false interruption resume enabled
  - LLM fallback from primary to smaller OpenAI model
  - TTS fallback from Sarvam to OpenAI
  - metrics/transcript/state/error logging

## 6. Master-Level Target Design

```text
Client
  LiveKit WebRTC microphone track

LiveKit Cloud
  Room routing, jitter handling, low-latency media

Agent Worker
  AgentSession
    turn_detection="stt"
    min_endpointing_delay=0.07
    allow_interruptions=true

  Sarvam STT
    language="unknown"
    model from env
    flush_signal=true

  OpenAI LLM
    primary conversational model
    fallback smaller model
    concise voice-oriented system prompt

  Sarvam TTS
    Bulbul voice from env
    OpenAI TTS fallback

Observability
  metrics_collected -> logs now, OTel/Prometheus later
  final transcripts -> logs now, redacted store later
  errors -> logs now, alerting later
```

Component responsibilities:

- `AgentSession`: orchestration, endpointing, interruptions, metrics events.
- `VoiceAgent`: system prompt and provider wiring.
- Sarvam STT: transcription plus speech boundary signals.
- OpenAI LLM: response generation.
- Sarvam TTS: primary Indian voice synthesis.
- Fallback adapters: graceful degradation.
- Observability handlers: production visibility without blocking the voice loop.

## 7. Tool Integration Design

No concrete tool was specified, so no tool was invented.

When adding tools:

- Use narrow LiveKit Agent tools for deterministic actions.
- Keep tool calls interrupt-aware.
- Log tool latency, success, and failure.
- Keep `max_tool_steps` conservative to avoid long dead air.
- For MCP, expose only tools needed for the voice task and summarize tool results before speaking.

## 8. Trade-Offs

Speed vs accuracy:

- Auto language detection improves multilingual usability but can be less deterministic than a fixed language.
- Short spoken responses reduce latency but may require follow-up questions.

Preemptive generation:

- The baseline keeps `preemptive_generation=False` because premature generation can answer partial speech.
- Enable only after measuring false-starts, interruption rate, and correction frequency.

Model quality vs latency:

- `gpt-4o` follows the workshop example for quality.
- `gpt-4o-mini` is a lower-cost fallback for degraded operation.

Reliability vs cost:

- Fallbacks improve uptime but can increase cost and voice consistency variance.
- TTS fallback may sound different; acceptable for resilience but should be monitored.

STT fallback risk:

- The workshop relies on Sarvam STT for turn signals. A non-Sarvam fallback may require a separate VAD or different turn detector, which changes the intended behavior.

## 9. Runbook

Install:

```powershell
pip install "livekit-agents[sarvam,openai,silero]" python-dotenv
```

Run the worker:

```powershell
python agent.py dev
```

Test locally:

```powershell
python agent.py console
```

Production checks:

- Validate `saaras:v3` and `bulbul:v3` against the installed Sarvam plugin.
- Measure p50/p95 end-of-utterance delay, LLM TTFT, TTS TTFB, and total time-to-first-audio.
- Rotate exposed keys and store future secrets only in a secret manager.
- Export metrics to Prometheus/OpenTelemetry instead of logs only.
