"""Tests for blue/red LLM client factories.

Each factory returns an LLMConfig (provider, plus per-provider fields).
Default provider is vllm (preserves the original Spark deployment);
setting BLUE_LLM_PROVIDER=bedrock or RED_LLM_PROVIDER=bedrock flips
the side to AWS Bedrock.
"""

from __future__ import annotations

from almighty_agent_runtime.llm_clients import (
    LLMConfig,
    build_blue_llm,
    build_red_llm,
)


# ----- vllm path (default) ---------------------------------------------------

def test_blue_llm_default_is_vllm_on_spark1():
    llm = build_blue_llm()
    assert isinstance(llm, LLMConfig)
    assert llm.provider == "vllm"
    assert "8001" in (llm.base_url or "")
    assert "127.0.0.1" in (llm.base_url or "") or "localhost" in (llm.base_url or "")
    assert "gemma-4-26B-A4B" in (llm.model or "")


def test_red_llm_default_is_vllm_on_spark2():
    llm = build_red_llm()
    assert llm.provider == "vllm"
    assert "8000" in (llm.base_url or "")
    assert "100.112.216.53" in (llm.base_url or "")
    assert "gemma-4-31B" in (llm.model or "")


def test_blue_llm_respects_base_url_override(monkeypatch):
    monkeypatch.setenv("BLUE_LLM_BASE_URL", "http://override:9000/v1")
    llm = build_blue_llm()
    assert llm.base_url == "http://override:9000/v1"


def test_red_llm_respects_base_url_override(monkeypatch):
    monkeypatch.setenv("RED_LLM_BASE_URL", "http://override:9001/v1")
    llm = build_red_llm()
    assert llm.base_url == "http://override:9001/v1"


# ----- bedrock path (demo-day fallback) -------------------------------------

def test_blue_llm_can_be_switched_to_bedrock(monkeypatch):
    monkeypatch.setenv("BLUE_LLM_PROVIDER", "bedrock")
    llm = build_blue_llm()
    assert llm.provider == "bedrock"
    assert "claude-sonnet-4-5" in (llm.model_id or "")
    assert llm.region == "us-east-1"
    # vllm fields cleared on the bedrock path
    assert llm.base_url is None
    assert llm.model is None


def test_red_llm_can_be_switched_to_bedrock(monkeypatch):
    monkeypatch.setenv("RED_LLM_PROVIDER", "bedrock")
    llm = build_red_llm()
    assert llm.provider == "bedrock"
    assert "claude-sonnet-4-5" in (llm.model_id or "")


def test_bedrock_model_id_overridable(monkeypatch):
    monkeypatch.setenv("BLUE_LLM_PROVIDER", "bedrock")
    monkeypatch.setenv("BLUE_LLM_MODEL_ID", "us.anthropic.claude-3-5-haiku-20241022-v1:0")
    llm = build_blue_llm()
    assert llm.model_id == "us.anthropic.claude-3-5-haiku-20241022-v1:0"


def test_bedrock_region_overridable(monkeypatch):
    monkeypatch.setenv("BLUE_LLM_PROVIDER", "bedrock")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    llm = build_blue_llm()
    assert llm.region == "us-west-2"
