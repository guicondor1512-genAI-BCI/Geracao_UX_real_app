"""Orquestrador: LangChain Deep Agent sobre o workspace, com o projeto alvo montado em /project/ quando informado."""

import os
from pathlib import Path
from typing import cast

from deepagents import SubAgent, create_deep_agent
from langchain.chat_models import init_chat_model

from app.models import fallback_middleware, model_name
from app.project import backend
from app.subagents import SUBAGENTS
from app.tools.plan_tool import plan_tool
from app.tools.project_check import project_check
from app.workspace import checkpointer, ensure, validate_skills

ORCHESTRATOR_PROMPT = """Você é o orquestrador de construção do front-end Angular 22 do Job Applier e da sua integração com o backend.
Workspace: /current/spec.md (protótipo front-end do ux-deep-agents), /current/screens.json, /current/reference/ (protótipo anterior),
/outputs/frontend/ (app Angular gerado; o projeto base já existe lá: package.json, angular.json, tsconfig, main.ts, index.html,
environments, app.config.ts; nunca os reescreva). Quando um projeto alvo é informado, ele está montado em /project/.

O pipeline externo (LangGraph) te chama em fases. Faça SOMENTE o que a mensagem da fase pedir. Delegue com a tool `task`:
- DESCRIBE:  plan_tool -> task(backend_analyst) escreve /outputs/brief/<slug>-descricao.md a partir de /project/. Confira as seções. Pare.
- PLANO:     leia a spec; plan_tool (/current/plan.md: telas, lotes, subagents); task(architect). Pare.
- BUILD:     leia /current/architecture.md; UMA task(angular_coder) POR LOTE de telas NA MESMA MENSAGEM (paralelo), cada uma com
             ids das telas, caminhos/classes exatos e componentes de /shared disponíveis. Depois confira com ls que cada tela de
             app.routes.ts existe e escreva /outputs/frontend/README.md (como rodar, tela -> rota -> arquivo, useMocks/apiBaseUrl, TODOs). Pare.
- FIX:       agrupe os erros do ngc por arquivo e dispare task(angular_coder) por grupo (paralelo) para corrigir só o citado. Pare.
- INTEGRATE: task(integrator) adapta backend (/project/) e front-end entregue para funcionarem juntos e roda project_check até passar. Pare.
Regras: não invente telas, campos ou rotas fora da spec e do código; marque suposições com [ASSUMPTION]; respostas curtas e acionáveis."""

TOOLS = {"project_check": project_check}


def _model(agent: str):
    """Modelo do agente com retries do SDK (backoff em 429/5xx/timeout); vale para orquestrador e subagents."""
    return init_chat_model(model_name(agent), streaming=True, max_retries=int(os.getenv("MODEL_MAX_RETRIES", "5")))


def _subagent(spec: dict) -> SubAgent:
    tools = [TOOLS[name] for name in spec.get("tools", [])]
    model = spec["name"]
    return cast(
        SubAgent, {**spec, "tools": tools, "model": _model(model), "middleware": fallback_middleware(model_name(model))}
    )


def build_agent(project_dir: Path | None = None):
    ensure()
    validate_skills()
    return create_deep_agent(
        model=_model("orchestrator"),
        tools=[plan_tool],
        system_prompt=ORCHESTRATOR_PROMPT,
        middleware=fallback_middleware(model_name("orchestrator")),
        subagents=[_subagent(s) for s in SUBAGENTS],
        skills=["/skills/"],
        backend=backend(project_dir),
        name="frontend-builder",
        checkpointer=checkpointer(),
    )
