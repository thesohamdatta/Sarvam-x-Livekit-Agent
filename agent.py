from __future__ import annotations

import logging
import os
from typing import Any

from dotenv import load_dotenv
from livekit.agents import JobContext, WorkerOptions, cli, llm, tts
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import openai, sarvam


load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("bulbul-sarvam-agent")


SYSTEM_PROMPT = """
You are a real-time Indian voice AI assistant.

Conversation style:
- Be warm, concise, and natural for spoken conversation.
- Prefer short responses: usually one to three sentences.
- Ask at most one clarifying question when needed.
- Handle code-mixed Indian speech naturally, including Hinglish and other mixed-language phrasing.
- Do not over-explain unless the user asks for detail.

Real-time constraints:
- Optimize for low-latency voice interaction.
- Start with the most useful answer, then add detail only if needed.
- If interrupted, stop cleanly and respond to the latest user intent.
- Avoid long lists in speech unless the user explicitly asks.

Accuracy constraints:
- Be explicit when uncertain.
- Never invent API results, account status, or tool output.
- For operational actions, confirm only when the action is irreversible or ambiguous.
""".strip()


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def build_stt() -> sarvam.STT:
    return sarvam.STT(
        language=os.getenv("SARVAM_STT_LANGUAGE", "unknown"),
        model=os.getenv("SARVAM_STT_MODEL", "saaras:v3"),
        api_key=required_env("SARVAM_API_KEY"),
        flush_signal=True,
        sample_rate=16000,
    )


def build_llm() -> llm.LLM:
    primary = openai.LLM(
        model=os.getenv("OPENAI_PRIMARY_LLM", "gpt-4o"),
        api_key=required_env("OPENAI_API_KEY"),
        temperature=0.4,
        timeout=8.0,
        max_retries=1,
    )
    fallback = openai.LLM(
        model=os.getenv("OPENAI_FALLBACK_LLM", "gpt-4o-mini"),
        api_key=required_env("OPENAI_API_KEY"),
        temperature=0.4,
        timeout=8.0,
        max_retries=1,
    )
    return llm.FallbackAdapter(
        [primary, fallback],
        attempt_timeout=5.0,
        max_retry_per_llm=0,
        retry_interval=0.25,
    )


def build_tts() -> tts.TTS:
    primary = sarvam.TTS(
        target_language_code=os.getenv("SARVAM_TTS_LANGUAGE", "en-IN"),
        model=os.getenv("SARVAM_TTS_MODEL", "bulbul:v3"),
        speaker=os.getenv("SARVAM_TTS_SPEAKER", "shubh"),
        api_key=required_env("SARVAM_API_KEY"),
        speech_sample_rate=22050,
        pace=1.0,
    )
    fallback = openai.TTS(
        model="gpt-4o-mini-tts",
        voice="ash",
        api_key=required_env("OPENAI_API_KEY"),
        speed=1.0,
        instructions="Natural, concise Indian English voice assistant delivery.",
    )
    return tts.FallbackAdapter([primary, fallback], max_retry_per_tts=1)


class VoiceAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=SYSTEM_PROMPT,
            stt=build_stt(),
            llm=build_llm(),
            tts=build_tts(),
        )

    async def on_enter(self) -> None:
        self.session.generate_reply(
            instructions="Greet the user briefly and ask how you can help."
        )


def attach_observability(session: AgentSession[Any]) -> None:
    @session.on("metrics_collected")
    def on_metrics(event: Any) -> None:
        metrics = event.metrics
        payload = metrics.model_dump() if hasattr(metrics, "model_dump") else vars(metrics)
        logger.info("metric=%s payload=%s", getattr(metrics, "type", "unknown"), payload)

    @session.on("user_input_transcribed")
    def on_transcript(event: Any) -> None:
        if event.is_final:
            logger.info(
                "final_user_transcript speaker=%s language=%s text=%r",
                event.speaker_id,
                event.language,
                event.transcript,
            )

    @session.on("agent_state_changed")
    def on_agent_state(event: Any) -> None:
        logger.info("agent_state %s -> %s", event.old_state, event.new_state)

    @session.on("error")
    def on_error(event: Any) -> None:
        logger.exception("pipeline_error source=%s error=%s", event.source, event.error)


async def entrypoint(ctx: JobContext) -> None:
    logger.info("worker_joined room=%s", ctx.room.name)

    session: AgentSession[Any] = AgentSession(
        turn_detection="stt",
        min_endpointing_delay=0.07,
        max_endpointing_delay=1.2,
        allow_interruptions=True,
        min_interruption_duration=0.25,
        false_interruption_timeout=1.0,
        resume_false_interruption=True,
        preemptive_generation=False,
    )
    attach_observability(session)

    await session.start(agent=VoiceAgent(), room=ctx.room)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
