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


def test_validate_skills(tmp_path, monkeypatch):
    from app import workspace as ws

    assert set(ws.validate_skills()) >= {"angular-app", "api-contract", "integration", "ux-brief"}
    bad = ws.ROOT / "skills" / "broken"
    bad.mkdir()
    (bad / "SKILL.md").write_text("---\nname: broken\ndescription: a: b: c\n---\n")
    try:
        ws.validate_skills()
    except ValueError as e:
        assert "broken" in str(e)
    else:
        raise AssertionError("skill invalida deveria falhar")


def test_override(monkeypatch):
    monkeypatch.setenv("MODEL_INTEGRATOR", "openai:gpt-6-sol")
    assert model_name("integrator") == "openai:gpt-6-sol"
    assert model_name("architect") == "openai:gpt-6-luna"
