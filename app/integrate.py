"""Fase de integracao: o front-end entregue em <projeto>/frontend e o backend passam a funcionar juntos.

integrate_phase -> verify_integration --(erros, 1 rodada)--> integrate_fix -> verify_integration
Usado pelo grafo de build (apos deliver) e pelo comando `integrate` (sobre um front-end ja entregue).
"""

from pathlib import Path
from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from app import project
from app import workspace as ws
from app.graph import GraphContext, RunState, _invoke, _say, finalize
from app.tools import project_check as pc

CHECKS = ("format", "tests", "frontend_build")


def _frontend_rel(state: RunState) -> str:
    """Caminho do front-end como o agente o ve (/project/frontend) ou absoluto se estiver fora do projeto."""
    dest, proj = Path(state["dest_dir"]), Path(state["project_dir"])
    return f"/project/{dest.relative_to(proj)}" if dest.is_relative_to(proj) else str(dest)


def integrate_phase(state: RunState, runtime: Runtime[GraphContext]) -> RunState:
    pc.configure(Path(state["project_dir"]), Path(state["dest_dir"]))
    ws.log(state["run_id"], "integrate_phase_start")
    _say(
        runtime,
        "INTEGRATE: integrator adapta backend e front-end (CORS, static, environment, contrato) e roda as checagens.",
    )
    msg = _invoke(
        runtime,
        state,
        "integrate_phase",
        f"INTEGRATE: o backend esta em /project/ e o front-end Angular entregue em {_frontend_rel(state)}. "
        "Execute task(integrator) para fazer back e front funcionarem juntos seguindo a skill integration, "
        "rodando project_check ate 'format', 'tests' e 'frontend_build' passarem. "
        "Responda com a lista de arquivos alterados e o resultado das checagens.",
    )
    return {"final_message": msg}


def verify_integration(state: RunState, runtime: Runtime[GraphContext]) -> RunState:
    pc.configure(Path(state["project_dir"]), Path(state["dest_dir"]))
    errors: list[str] = []
    for kind in CHECKS:
        ok, out = pc.run_check(kind)
        ws.log(state["run_id"], "integration_check", kind=kind, ok=ok, output=out[-2000:])
        _say(runtime, f"   {kind}: {'ok' if ok else 'FALHOU'}")
        if not ok:
            errors.append(f"## {kind}\n{out}")
    return {"integration_errors": errors, "project_changes": project.git_diff_stat(Path(state["project_dir"]))}


def integrate_fix(state: RunState, runtime: Runtime[GraphContext]) -> RunState:
    ws.log(state["run_id"], "integrate_fix_start")
    _say(runtime, "INTEGRATE FIX: uma rodada de correcao sobre as checagens que falharam.")
    _invoke(
        runtime,
        state,
        "integrate_fix",
        "INTEGRATE FIX: as checagens abaixo falharam apos a integracao. Execute task(integrator) para corrigir "
        "apenas o necessario e rodar project_check de novo. Responda com o que mudou.\n\n"
        + "\n\n".join(state["integration_errors"]),
    )
    return {"integration_fixed": True}


def after_integration(state: RunState) -> Literal["integrate_fix", "finalize"]:
    if state["integration_errors"] and not state.get("integration_fixed"):
        return "integrate_fix"
    return "finalize"


def add_integration(g: StateGraph, after: str | None) -> None:
    """Liga integrate_phase -> verify_integration -> (integrate_fix | finalize) a um grafo que ja tem `finalize`."""
    g.add_node("integrate_phase", integrate_phase)
    g.add_node("verify_integration", verify_integration)
    g.add_node("integrate_fix", integrate_fix)
    if after:
        g.add_edge(after, "integrate_phase")
    g.add_edge("integrate_phase", "verify_integration")
    g.add_conditional_edges("verify_integration", after_integration)
    g.add_edge("integrate_fix", "verify_integration")


def ingest_integrate(state: RunState) -> RunState:
    """Comando `integrate` sozinho: usa o front-end ja entregue em dest_dir, sem limpar outputs/."""
    ws.ensure()
    ws.write_run_status(state["run_id"], "running")
    ws.write_metadata(
        state["run_id"], status="running", mode="integrate", project=state["project_dir"], dest=state["dest_dir"]
    )
    ws.log(state["run_id"], "ingest", mode="integrate", project=state["project_dir"], dest=state["dest_dir"])
    return {
        "fix_round": 0,
        "frontend_errors": [],
        "build_errors": [],
        "input_path": str(Path(state["dest_dir"]) / "README.md"),
    }


def build_integrate_graph():
    g = StateGraph(RunState, context_schema=GraphContext)
    g.add_node("ingest_integrate", ingest_integrate)
    g.add_node("finalize", finalize)
    g.add_edge(START, "ingest_integrate")
    add_integration(g, "ingest_integrate")
    g.add_edge("finalize", END)
    return g.compile(checkpointer=ws.checkpointer())
