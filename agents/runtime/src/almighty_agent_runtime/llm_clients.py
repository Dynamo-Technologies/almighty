"""Per-side LLM client factories pointing at the Sparks' vLLM endpoints.

Blue → spark-763d localhost (CrewAI worker is co-located on this Spark).
Red  → spark-3fe3 over the Spark-to-Spark cable.

Both endpoints expose OpenAI-compatible /v1/chat/completions with
tool-calling enabled (--enable-auto-tool-choice --tool-call-parser
gemma4), verified during pre-flight.

The `hosted_vllm/...` provider prefix is CrewAI's native handler for
self-hosted vLLM endpoints (no litellm dependency).
"""

from __future__ import annotations

import os

from crewai import LLM


_BLUE_DEFAULT_BASE = "http://127.0.0.1:8001/v1"
_RED_DEFAULT_BASE = "http://100.112.216.53:8000/v1"


def build_blue_llm() -> LLM:
    """Gemma 4 26B-A4B-it on spark-763d via localhost vLLM."""
    return LLM(
        model="hosted_vllm/google/gemma-4-26B-A4B-it",
        base_url=os.environ.get("BLUE_LLM_BASE_URL", _BLUE_DEFAULT_BASE),
        api_key=os.environ.get("BLUE_LLM_API_KEY", "EMPTY"),
        temperature=0.3,
    )


def build_red_llm() -> LLM:
    """Gemma 4 31B-it on spark-3fe3 via the Spark-to-Spark cable."""
    return LLM(
        model="hosted_vllm/google/gemma-4-31B-it",
        base_url=os.environ.get("RED_LLM_BASE_URL", _RED_DEFAULT_BASE),
        api_key=os.environ.get("RED_LLM_API_KEY", "EMPTY"),
        temperature=0.4,
    )
