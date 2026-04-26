"""Tests for blue/red LLM client factories.

Each factory returns a CrewAI `LLM` configured for the right Spark.
The test asserts on `.base_url` and `.model` attributes — both exist on
the OpenAICompatibleCompletion that CrewAI returns for `hosted_vllm/...`
provider strings.
"""

from __future__ import annotations

from almighty_agent_runtime.llm_clients import build_blue_llm, build_red_llm


def test_blue_llm_targets_local_vllm_on_spark1():
    llm = build_blue_llm()
    assert "8001" in llm.base_url
    assert "127.0.0.1" in llm.base_url or "localhost" in llm.base_url
    # Provider strips the `hosted_vllm/` prefix from .model
    assert "gemma-4-26B-A4B" in llm.model


def test_red_llm_targets_spark2_over_cable():
    llm = build_red_llm()
    assert "8000" in llm.base_url
    # spark-3fe3 tailscale IP per spec §3
    assert "100.112.216.53" in llm.base_url
    assert "gemma-4-31B" in llm.model


def test_blue_llm_respects_env_override(monkeypatch):
    monkeypatch.setenv("BLUE_LLM_BASE_URL", "http://override:9000/v1")
    llm = build_blue_llm()
    assert llm.base_url == "http://override:9000/v1"


def test_red_llm_respects_env_override(monkeypatch):
    monkeypatch.setenv("RED_LLM_BASE_URL", "http://override:9001/v1")
    llm = build_red_llm()
    assert llm.base_url == "http://override:9001/v1"
