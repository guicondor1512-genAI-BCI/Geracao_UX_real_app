"""Modelo por agente: MODEL_<AGENTE> no ambiente sobrescreve o default (todos em gpt-6-luna)."""

import os

LUNA = "openai:gpt-6-luna"

DEFAULTS = {
    "orchestrator": LUNA,
    "architect": LUNA,
    "angular_coder": LUNA,
    "backend_analyst": LUNA,
    "integrator": LUNA,
}
"""gpt-6-luna e o modelo mais barato da familia GPT-6 (US$ 0,10 / 0,50 por 1M tokens) e gerou o prototipo Angular
do ux-deep-agents compilando com strictTemplates; troque uma entrada para rotear um agente a outro modelo."""


def model_name(agent: str) -> str:
    """MODEL_<AGENTE> > MODEL (so para o orquestrador) > default. Formato init_chat_model (provider:modelo)."""
    override = os.getenv(f"MODEL_{agent.upper()}")
    if override:
        return override
    if agent == "orchestrator" and os.getenv("MODEL"):
        return os.environ["MODEL"]
    return DEFAULTS[agent]
