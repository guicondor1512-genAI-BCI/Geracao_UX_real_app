"""Grafo `describe`: le o backend do projeto e gera o .md que orienta o designer a prototipar as telas.

ingest_project -> describe_phase -> finalize_describe
"""

import os
import shutil
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from app import project
from app import workspace as ws
from app.graph import GraphContext, _invoke, _say

UX_INPUTS_DIR = Path(os.getenv("UX_INPUTS_DIR", "~/UX Project/ux-deep-agents/workspace/inputs")).expanduser()
BRIEF = "outputs/brief"


class DescribeState(TypedDict, total=False):
    project_dir: str
    run_id: str
    to_ux: bool
    brief_path: str
    final_message: str
    run_dir: str


def ingest_project(state: DescribeState) -> DescribeState:
    ws.ensure()
    ws.clear_current()
    ws.clear_outputs()
    (ws.ROOT / BRIEF).mkdir(parents=True)
    ws.write_run_status(state["run_id"], "running")
    ws.write_metadata(state["run_id"], status="running", mode="describe", project=state["project_dir"])
    ws.log(state["run_id"], "ingest", mode="describe", project=state["project_dir"])
    return {}


def describe_phase(state: DescribeState, runtime: Runtime[GraphContext]) -> DescribeState:
    name = project.slug(Path(state["project_dir"]))
    _say(runtime, "DESCRIBE: backend_analyst le o projeto e escreve o brief para o designer. Alguns minutos.")
    msg = _invoke(
        runtime,
        state,
        "describe_phase",
        f"DESCRIBE: o projeto alvo esta montado em /project/. Registre o plano com plan_tool e execute "
        f"task(backend_analyst) para escrever /outputs/brief/{name}-descricao.md seguindo a skill ux-brief. "
        "Quando retornar, leia o arquivo e confira que todas as secoes da skill existem; se faltar algo, peca a "
        "correcao ao mesmo subagent. Responda com um resumo de 5 linhas do que o brief cobre.",
    )
    return {"final_message": msg}


def finalize_describe(state: DescribeState) -> DescribeState:
    run_id = state["run_id"]
    briefs = sorted((ws.ROOT / BRIEF).glob("*.md"))
    if not briefs:
        ws.write_run_status(run_id, "failed")
        ws.write_metadata(run_id, status="failed", error="nenhum .md em outputs/brief")
        raise RuntimeError("O agente nao escreveu o brief em outputs/brief/")
    brief = briefs[0]
    copies = [shutil.copy2(brief, ws.ROOT / "inputs" / brief.name)]
    if state.get("to_ux") and UX_INPUTS_DIR.exists():
        copies.append(shutil.copy2(brief, UX_INPUTS_DIR / brief.name))
    ws.write_run_status(run_id, "done")
    run_dir = ws.snapshot_run(run_id, brief)
    report = ws.usage_report(run_id)
    ws.write_metadata(run_id, status="done", brief=str(brief), copies=[str(c) for c in copies], usage=report["totals"])
    ws.log(run_id, "finalize", brief=str(brief), copies=[str(c) for c in copies], **report["totals"])
    return {"brief_path": str(brief), "run_dir": str(run_dir)}


def build_describe_graph():
    g = StateGraph(DescribeState, context_schema=GraphContext)
    g.add_node("ingest_project", ingest_project)
    g.add_node("describe_phase", describe_phase)
    g.add_node("finalize_describe", finalize_describe)
    g.add_edge(START, "ingest_project")
    g.add_edge("ingest_project", "describe_phase")
    g.add_edge("describe_phase", "finalize_describe")
    g.add_edge("finalize_describe", END)
    return g.compile(checkpointer=ws.checkpointer())
