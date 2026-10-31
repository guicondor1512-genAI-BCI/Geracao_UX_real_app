"""Todo subagent precisa de um modelo em DEFAULTS; MODEL_<AGENTE> sobrescreve."""

from app.models import DEFAULTS, model_name
from app.subagents import SUBAGENTS


def test_every_subagent_has_a_model():
    assert {s["name"] for s in SUBAGENTS} <= set(DEFAULTS)


def test_override(monkeypatch):
    monkeypatch.setenv("MODEL_INTEGRATOR", "openai:gpt-6-sol")
    assert model_name("integrator") == "openai:gpt-6-sol"
    assert model_name("architect") == "openai:gpt-6-luna"
