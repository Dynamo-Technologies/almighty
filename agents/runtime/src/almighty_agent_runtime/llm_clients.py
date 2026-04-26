"""Per-side LLM client factories.

Two providers supported:
  - vllm    — OpenAI-compatible /v1/chat/completions on a self-hosted
              endpoint. The hackathon's original target (Gemma 4 on the
              NVIDIA Sparks).
  - bedrock — AWS Bedrock Converse API. Used as the demo-day fallback
              when the Sparks are unreachable; same crew code runs
              against Anthropic Claude Sonnet 4.5 with no other changes.

Provider is selected per side via env var (BLUE_LLM_PROVIDER /
RED_LLM_PROVIDER). Default is vllm; production demo on EC2 sets both
to "bedrock".
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class LLMConfig:
    """Provider-agnostic LLM target. llm_step.py dispatches on .provider."""
    provider: str  # "vllm" | "bedrock"
    temperature: float = 0.3
    # vllm fields (None for bedrock)
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    # bedrock fields (None for vllm)
    model_id: str | None = None
    region: str | None = None


# Defaults preserved from the original Spark deployment.
_BLUE_VLLM_DEFAULT_BASE = "http://127.0.0.1:8001/v1"
_RED_VLLM_DEFAULT_BASE = "http://100.112.216.53:8000/v1"

# Cross-region inference profile for Claude Sonnet 4.5 — routes across
# us-east-1 / us-east-2 / us-west-2 for availability.
_BEDROCK_DEFAULT_MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"


def build_blue_llm() -> LLMConfig:
    """Build the LLM config for the blue battalion S3."""
    provider = os.environ.get("BLUE_LLM_PROVIDER", "vllm")
    if provider == "bedrock":
        return LLMConfig(
            provider="bedrock",
            model_id=os.environ.get("BLUE_LLM_MODEL_ID", _BEDROCK_DEFAULT_MODEL_ID),
            region=os.environ.get("AWS_REGION", "us-east-1"),
            temperature=0.3,
        )
    return LLMConfig(
        provider="vllm",
        model="hosted_vllm/google/gemma-4-26B-A4B-it",
        base_url=os.environ.get("BLUE_LLM_BASE_URL", _BLUE_VLLM_DEFAULT_BASE),
        api_key=os.environ.get("BLUE_LLM_API_KEY", "EMPTY"),
        temperature=0.3,
    )


def build_red_llm() -> LLMConfig:
    """Build the LLM config for the red battalion S3."""
    provider = os.environ.get("RED_LLM_PROVIDER", "vllm")
    if provider == "bedrock":
        return LLMConfig(
            provider="bedrock",
            model_id=os.environ.get("RED_LLM_MODEL_ID", _BEDROCK_DEFAULT_MODEL_ID),
            region=os.environ.get("AWS_REGION", "us-east-1"),
            temperature=0.4,
        )
    return LLMConfig(
        provider="vllm",
        model="hosted_vllm/google/gemma-4-31B-it",
        base_url=os.environ.get("RED_LLM_BASE_URL", _RED_VLLM_DEFAULT_BASE),
        api_key=os.environ.get("RED_LLM_API_KEY", "EMPTY"),
        temperature=0.4,
    )
