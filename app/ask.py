"""Perguntas e respostas: um deep agent so de leitura sobre o workspace do builder e, se montado, o projeto alvo."""

import os
from pathlib import Path

from deepagents import FilesystemPermission, create_deep_agent
from langchain.chat_models import init_chat_model

from app.models import model_name
from app.project import backend
from app.workspace import ensure

READ_ONLY = FilesystemPermission(operations=["write"], paths=["/**"], mode="deny")
PROMPT = """Você responde perguntas sobre o frontend-builder, suas execuções e o projeto alvo. Fontes (raiz virtual '/'):
- /metadata/<run_id>.json: status, modo, uso de tokens, arquivos gerados, erros de integração e git status de cada run;
- /logs/<run_id>.jsonl: eventos de cada run, com duração, tokens por fase e erros do ngc e das checagens;
- /current/: spec.md, screens.json, plan.md e architecture.md da run atual; /outputs/: front-end gerado ou brief;
- /runs/<run_id>/: snapshot de cada run; /skills/: regras que os subagents seguem;
- /project/: backend e front-end do projeto alvo, quando montado.
Use ls, glob, grep e read_file para achar a resposta; você não pode escrever arquivos. Responda em português, curto e
factual, citando os arquivos que usou; quando não houver dado, diga que não há em vez de supor."""


def build_ask_agent(project_dir: Path | None = None):
    ensure()
    model = init_chat_model(model_name("ask"), max_retries=int(os.getenv("MODEL_MAX_RETRIES", "5")))
    return create_deep_agent(
        model=model,
        system_prompt=PROMPT,
        backend=backend(project_dir),
        permissions=[READ_ONLY],
        name="frontend-builder-ask",
    )


def run_agent(question: str, project_dir: Path | None = None, agent=None) -> str:
    """Resposta em texto do agente para uma pergunta; `agent` permite injetar um falso nos testes."""
    agent = agent or build_ask_agent(project_dir)
    result = agent.invoke({"messages": [{"role": "user", "content": question}]}, config={"recursion_limit": 60})
    last = result["messages"][-1]
    return last.text if hasattr(last, "text") else str(last.content)
