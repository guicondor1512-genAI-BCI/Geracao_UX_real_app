"""Modelo por agente (todos em gpt-6-luna; MODEL_<AGENTE> sobrescreve) e fallback do mesmo modelo no OpenRouter.

Quando a OpenAI responde 429 (limite de tokens por minuto, comum com varios angular_coder em paralelo) ou 5xx apos os
retries do SDK, a chamada e repetida no mesmo modelo servido pelo OpenRouter, se OPENROUTER_API_KEY estiver no ambiente.
"""

import os

from langchain.agents.middleware import AgentMiddleware, ModelFallbackMiddleware
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

LUNA = "openai:gpt-6-luna"
OPENROUTER_URL = "https://openrouter.ai/api/v1"

DEFAULTS = {
    "orchestrator": LUNA,
    "architect": LUNA,
    "angular_coder": LUNA,
    "backend_analyst": LUNA,
    "integrator": LUNA,
    "ask": LUNA,
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


def openrouter_twin(model: str) -> ChatOpenAI | None:
    """O mesmo modelo no OpenRouter (openai:gpt-6-luna -> openai/gpt-6-luna); None sem OPENROUTER_API_KEY."""
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        return None
    return ChatOpenAI(model=model.replace(":", "/", 1), base_url=OPENROUTER_URL, api_key=SecretStr(key))


def fallback_middleware(model: str) -> list[AgentMiddleware]:
    """Middleware que repete uma chamada que falhou no twin do OpenRouter; lista vazia sem a chave."""
    twin = openrouter_twin(model)
    return [ModelFallbackMiddleware(twin)] if twin else []
