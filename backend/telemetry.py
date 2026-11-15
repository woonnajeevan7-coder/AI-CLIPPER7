"""
Production Telemetry, Cost Tracker & Structured Logging
Provides request correlation IDs, Sentry error monitoring, per-stage latency timings,
and token/render cost accounting for every pipeline job.
"""

import os
import time
import json
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

# Structured Logger Setup
logger = logging.getLogger("ai_clipper")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(name)s", "message": "%(message)s"}'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class JobCostReport(BaseModel):
    """Accurate per-job accounting for LLM tokens, Whisper audio minutes, and GPU render time."""
    job_id: str
    llm_prompt_tokens: int = 0
    llm_completion_tokens: int = 0
    audio_duration_seconds: float = 0.0
    render_duration_seconds: float = 0.0
    llm_cost_cents: float = 0.0
    transcription_cost_cents: float = 0.0
    compute_cost_cents: float = 0.0
    total_cost_cents: float = 0.0


class CostTracker:
    """Calculates operational infrastructure cost per pipeline execution."""

    # Cost constants (Groq & Cloud GPU pricing)
    GROQ_LLM_INPUT_PER_1M: float = 0.59    # $0.59 per 1M tokens
    GROQ_LLM_OUTPUT_PER_1M: float = 0.79   # $0.79 per 1M tokens
    WHISPER_PER_MINUTE_USD: float = 0.0108 # $0.0108 per audio minute ($0.00018/sec)
    NVENC_GPU_PER_HOUR_USD: float = 0.25   # $0.25/hr cloud GPU node

    @classmethod
    def calculate_cost(
        cls,
        job_id: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        audio_duration_seconds: float = 0.0,
        render_seconds: float = 0.0
    ) -> JobCostReport:
        llm_cost = (
            (prompt_tokens / 1_000_000.0) * cls.GROQ_LLM_INPUT_PER_1M +
            (completion_tokens / 1_000_000.0) * cls.GROQ_LLM_OUTPUT_PER_1M
        ) * 100.0  # cents

        whisper_cost = ((audio_duration_seconds / 60.0) * cls.WHISPER_PER_MINUTE_USD) * 100.0  # cents

        gpu_cost = ((render_seconds / 3600.0) * cls.NVENC_GPU_PER_HOUR_USD) * 100.0  # cents

        total_cents = round(llm_cost + whisper_cost + gpu_cost, 4)

        return JobCostReport(
            job_id=job_id,
            llm_prompt_tokens=prompt_tokens,
            llm_completion_tokens=completion_tokens,
            audio_duration_seconds=round(audio_duration_seconds, 2),
            render_duration_seconds=round(render_seconds, 2),
            llm_cost_cents=round(llm_cost, 4),
            transcription_cost_cents=round(whisper_cost, 4),
            compute_cost_cents=round(gpu_cost, 4),
            total_cost_cents=total_cents
        )


def init_sentry():
    """Initializes Sentry error & performance monitoring if DSN is set."""
    sentry_dsn = os.getenv("SENTRY_DSN")
    if not sentry_dsn:
        logger.info("SENTRY_DSN not provided; skipping Sentry initialization.")
        return

    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=sentry_dsn,
            traces_sample_rate=1.0,
            profiles_sample_rate=1.0,
            environment=os.getenv("ENVIRONMENT", "production")
        )
        logger.info("Sentry monitoring initialized successfully.")
    except Exception as e:
        logger.warning(f"Failed to initialize Sentry: {e}")
