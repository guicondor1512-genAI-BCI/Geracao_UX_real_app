"""Todo subagent precisa de um modelo em DEFAULTS; MODEL_<AGENTE> sobrescreve."""

from app.models import DEFAULTS, model_name
from app.subagents import SUBAGENTS


def test_every_subagent_has_a_model():
    assert {s["name"] for s in SUBAGENTS} <= set(DEFAULTS)


def test_fallback_only_with_openrouter_key(monkeypatch):
    from app.models import fallback_middleware

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert fallback_middleware("openai:gpt-6-luna") == []
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    (middleware,) = fallback_middleware("openai:gpt-6-luna")
    assert middleware.models[0].model_name == "openai/gpt-6-luna"


def test_override(monkeypatch):
    monkeypatch.setenv("MODEL_INTEGRATOR", "openai:gpt-6-sol")
    assert model_name("integrator") == "openai:gpt-6-sol"
    assert model_name("architect") == "openai:gpt-6-luna"
