"""Pipeline LangGraph do builder:

ingest -> plan_phase -> review_architecture --(aprovado | auto_approve)--> build_phase -> verify_frontend --(erros)--> fix_phase
                              ^        |                                                        '--(ok)--> deliver
                              '-- revise_architecture <-- (feedback, ate MAX_REVIEW_ROUNDS)      -> [integrate_phase -> verify_integration] -> finalize
A integracao (app/integrate.py) so entra quando um projeto alvo (--project) e informado.
"""

import json
import os
import shutil
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypedDict

from langchain_core.callbacks import BaseCallbackHandler, UsageMetadataCallbackHandler
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import interrupt

from app import contract, ratelimit, spec, theme
from app import frontend_check as fc
from app import workspace as ws

MAX_FIX_ROUNDS = int(os.getenv("MAX_FIX_ROUNDS", "5"))
MAX_REVIEW_ROUNDS = int(os.getenv("MAX_REVIEW_ROUNDS", "3"))
DEFAULT_REJECTION = "Reprovado sem comentario."


class RunState(TypedDict, total=False):
    input_path: str
    screens_path: str
    reference_dir: str
    stitch_dir: str
    dest_dir: str
    project_dir: str
    run_id: str
    auto_approve: bool
    review_round: int
    approved: bool
    forced_build: bool
    feedback: list[str]
    fix_round: int
    frontend_errors: list[str]
    build_errors: list[str]
    integration_errors: list[str]
    integration_fixed: bool
    project_changes: str
    final_message: str
    run_dir: str


@dataclass
class GraphContext:
    """Dependencias injetadas em graph.invoke(..., context=GraphContext(agent=...)); nao entram no checkpoint."""

    agent: Any
    notify: Callable[[str], None] | None = None


def _say(runtime: Runtime[GraphContext], text: str) -> None:
    if runtime.context.notify:
        runtime.context.notify(text)


class _Progress(BaseCallbackHandler):
    """Avisa quando cada subagent (tool `task`) comeca e termina."""

    def __init__(self, notify: Callable[[str], None]):
        self.notify = notify
        self.started: dict = {}

    def on_tool_start(self, serialized, input_str, *, run_id, inputs=None, **kwargs):
        if (serialized or {}).get("name") == "task":
            name = (inputs or {}).get("subagent_type") or "subagent"
            self.started[run_id] = (name, time.perf_counter())
            self.notify(f"   -> {name} iniciou: {((inputs or {}).get('description') or '')[:90]}")

    def on_tool_end(self, output, *, run_id, **kwargs):
        if run_id in self.started:
            name, t0 = self.started.pop(run_id)
            self.notify(f"   <- {name} terminou ({time.perf_counter() - t0:.0f}s)")

    def on_tool_error(self, error, *, run_id, **kwargs):
        if run_id in self.started:
            name, _ = self.started.pop(run_id)
            self.notify(f"   <- {name} falhou: {type(error).__name__}")


def _tokens(usage: UsageMetadataCallbackHandler) -> dict:
    totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for m in usage.usage_metadata.values():  # UsageMetadata (TypedDict) por modelo
        totals["input_tokens"] += m["input_tokens"]
        totals["output_tokens"] += m["output_tokens"]
        totals["total_tokens"] += m["total_tokens"]
    return {**totals, "models": {name: m["total_tokens"] for name, m in usage.usage_metadata.items()}}


def _parallel_task_calls(messages: list) -> int:
    """Mensagens do orquestrador com 2+ task() de uma vez (evidencia de subagents em paralelo)."""
    return sum(
        1 for m in messages if len([c for c in getattr(m, "tool_calls", None) or [] if c.get("name") == "task"]) >= 2
    )


def _invoke(runtime: Runtime[GraphContext], state: Mapping[str, Any], phase: str, instruction: str) -> str:
    """Invoca o deep agent na mesma thread por run e grava `<phase>_end` com duracao e tokens; falha vira `failed`."""
    usage = UsageMetadataCallbackHandler()
    callbacks: list = [usage]
    if runtime.context.notify:
        callbacks.append(_Progress(runtime.context.notify))
    started = time.perf_counter()
    try:
        result = runtime.context.agent.invoke(
            {"messages": [{"role": "user", "content": instruction}]},
            config={
                "recursion_limit": 300,
                "callbacks": callbacks,
                "run_name": f"{state['run_id']}:{phase}",
                "tags": [state["run_id"], phase],
                "metadata": {"builder_run_id": state["run_id"], "phase": phase},
                "configurable": {"thread_id": f"{state['run_id']}-agent"},
            },
        )
    except Exception as e:
        ws.log(
            state["run_id"], "failed", phase=phase, error_type=type(e).__name__, error=str(e)[:2000], **_tokens(usage)
        )
        ws.write_run_status(state["run_id"], "failed")
        ws.write_metadata(state["run_id"], status="failed", failed_phase=phase, error=str(e)[:500])
        raise
    last = result["messages"][-1]
    msg = last.text if hasattr(last, "text") else str(last.content)
    ws.log(
        state["run_id"],
        f"{phase}_end",
        summary=msg,
        duration_s=round(time.perf_counter() - started, 1),
        parallel_task_calls=_parallel_task_calls(result["messages"]),
        **_tokens(usage),
        **ratelimit.stats(),
    )
    return msg


# ---------------- nos ----------------
def ingest(state: RunState) -> RunState:
    """Limpa current/ e outputs/, copia spec, screens.json e referencia; prepara o projeto Angular base."""
    ws.ensure()
    run_id = state["run_id"]
    ws.clear_current()
    ws.clear_outputs()
    current = ws.ROOT / "current"
    shutil.copy2(Path(state["input_path"]), current / "spec.md")
    ids: list[str] = []
    if state.get("screens_path"):
        shutil.copy2(Path(state["screens_path"]), current / "screens.json")
        ids = [s["id"] for s in json.loads(Path(state["screens_path"]).read_text(encoding="utf-8")).get("screens", [])]
    found = spec.write_sections(current / "spec.md", current / "screens", ids)
    if state.get("reference_dir"):
        shutil.copytree(
            Path(state["reference_dir"]),
            current / "reference",
            ignore=shutil.ignore_patterns("node_modules", ".angular", "dist", "*.json", "*.html", "*.css"),
        )
    frontend = ws.ROOT / ws.FRONTEND
    frontend.mkdir(parents=True)
    fc.scaffold(frontend)
    if state.get("project_dir"):
        api = contract.generate(Path(state["project_dir"]), current, frontend / "src" / "app" / "core" / "models.ts")
        ws.log(run_id, "openapi", **api)
    themed = False
    if state.get("stitch_dir"):
        shutil.copytree(Path(state["stitch_dir"]), current / "stitch", ignore=shutil.ignore_patterns("*.png", "*.md"))
        themed = theme.apply_theme(current / "stitch", frontend / "src" / "index.html", frontend / "src" / "styles.css")
    ws.write_run_status(run_id, "running")
    ws.write_metadata(
        run_id,
        status="running",
        input=state["input_path"],
        screens=state.get("screens_path"),
        reference=state.get("reference_dir"),
        stitch=state.get("stitch_dir"),
        dest=state.get("dest_dir") or str(ws.dest_dir()),
        project=state.get("project_dir"),
    )
    ws.log(
        run_id,
        "ingest",
        input=state["input_path"],
        screens=state.get("screens_path"),
        reference=state.get("reference_dir"),
        stitch=state.get("stitch_dir"),
        stitch_theme=themed,
        screen_sections=found,
    )
    return {"fix_round": 0, "frontend_errors": [], "build_errors": []}


def plan_phase(state: RunState, runtime: Runtime[GraphContext]) -> RunState:
    ws.log(state["run_id"], "plan_phase_start")
    _say(runtime, "PLANO: plan_tool -> architect (arquitetura + nucleo do app). Alguns minutos.")
    msg = _invoke(
        runtime,
        state,
        "plan_phase",
        "PLANO: leia /current/spec.md (e /current/screens.json, /current/reference se existirem). Registre o plano com "
        "plan_tool e execute task(architect) para escrever /current/architecture.md e o nucleo do app em /outputs/frontend. "
        "PARE depois disso: nao gere telas ainda. Responda com os lotes de telas propostos.",
    )
    return {"final_message": msg}


def _read(name: str) -> str:
    path = ws.ROOT / "current" / name
    return path.read_text(encoding="utf-8") if path.exists() else ""


def review_architecture(state: RunState) -> RunState:
    """Human-in-the-loop: pausa ate o revisor aprovar /current/architecture.md ou devolver feedback (D3)."""
    run_id = state["run_id"]
    if state.get("auto_approve"):
        ws.log(run_id, "review_skipped", reason="auto_approve")
        return {"approved": True, "review_round": state.get("review_round", 0), "feedback": state.get("feedback", [])}
    ws.write_run_status(run_id, "paused")
    ws.write_metadata(run_id, status="paused")
    decision = interrupt(
        {
            "question": "A arquitetura (telas, rotas, componentes, lotes) esta certa? Aprove ou devolva correcoes.",
            "round": state.get("review_round", 0) + 1,
            "max_rounds": MAX_REVIEW_ROUNDS,
            "summary": state.get("final_message", ""),
            "architecture": _read("architecture.md"),
            "plan": _read("plan.md"),
        }
    )
    ws.write_run_status(run_id, "running")
    ws.write_metadata(run_id, status="running")
    approved = bool(decision.get("approved"))
    feedback = (decision.get("feedback") or "").strip()
    if not approved and not feedback:
        feedback = DEFAULT_REJECTION
    round_ = state.get("review_round", 0) + 1
    forced = not approved and round_ >= MAX_REVIEW_ROUNDS
    ws.log(run_id, "review_architecture", round=round_, approved=approved, feedback=feedback)
    if forced:
        ws.log(run_id, "forced_build", round=round_, max_rounds=MAX_REVIEW_ROUNDS)
    history = state.get("feedback", []) + ([feedback] if feedback else [])
    if feedback:
        (ws.ROOT / "current" / "feedback.md").write_text(
            "# Feedback do revisor\n\n" + "\n\n".join(f"## Rodada {i + 1}\n{f}" for i, f in enumerate(history)),
            encoding="utf-8",
        )
    return {"approved": approved, "feedback": history, "review_round": round_, "forced_build": forced}


def revise_architecture(state: RunState, runtime: Runtime[GraphContext]) -> RunState:
    ws.log(state["run_id"], "revise_start", round=state["review_round"])
    _say(runtime, f"REVISAO (rodada {state['review_round']}/{MAX_REVIEW_ROUNDS}): architect revisa com o seu feedback.")
    msg = _invoke(
        runtime,
        state,
        f"revise_{state['review_round']}",
        "REVISAO: o revisor NAO aprovou a arquitetura. Leia /current/feedback.md, atualize /current/plan.md e execute "
        "task(architect) para revisar /current/architecture.md e o nucleo do app em /outputs/frontend conforme o "
        "feedback (edite o que mudou, nao reescreva o resto). PARE depois disso. Resuma o que mudou.",
    )
    return {"final_message": msg}


def after_review(state: RunState) -> Literal["build_phase", "revise_architecture"]:
    if state.get("approved") or state.get("review_round", 0) >= MAX_REVIEW_ROUNDS:
        return "build_phase"
    return "revise_architecture"


def build_phase(state: RunState, runtime: Runtime[GraphContext]) -> RunState:
    ws.log(state["run_id"], "build_phase_start", forced=state.get("forced_build", False))
    _say(runtime, "BUILD: angular_coder em paralelo, um lote de telas por task; depois README.md.")
    msg = _invoke(
        runtime,
        state,
        "build_phase",
        "BUILD: leia /current/architecture.md e dispare UMA task(angular_coder) por lote de telas NA MESMA MENSAGEM "
        "(em paralelo), cada uma com os ids das telas, os caminhos/classes exatos e os componentes de /shared disponiveis. "
        "Quando todas retornarem, confira com ls que todas as telas de app.routes.ts existem (gere as que faltarem) e "
        "escreva /outputs/frontend/README.md. Responda com a lista de telas geradas."
        + (
            " ATENCAO: o revisor NAO aprovou a arquitetura dentro do limite de rodadas; /current/feedback.md traz as "
            "pendencias abertas, repasse-as aos angular_coder."
            if state.get("forced_build")
            else " Se /current/feedback.md existir, repasse-o na instrucao de cada angular_coder."
        ),
    )
    return {"final_message": msg}


def verify_frontend(state: RunState, runtime: Runtime[GraphContext]) -> RunState:
    """ngc --noEmit sobre /outputs/frontend; erros vao para fix_phase ate MAX_FIX_ROUNDS."""
    run_id = state["run_id"]
    frontend = ws.ROOT / ws.FRONTEND
    if os.getenv("FRONTEND_CHECK", "1") != "1" or not fc.available():
        ws.log(run_id, "frontend_check_skipped", reason="FRONTEND_CHECK=0" if fc.available() else "npm ausente")
        return {"frontend_errors": []}
    _say(runtime, "VERIFY: ngc --noEmit (na 1a vez instala as dependencias, ~1 min).")
    errors = fc.check_frontend(frontend)
    ws.log(run_id, "frontend_check", round=state["fix_round"], ok=not errors, errors=errors)
    _say(runtime, "   ok: compila" if not errors else f"   {len(errors)} linha(s) de erro")
    return {"frontend_errors": errors}


def fix_phase(state: RunState, runtime: Runtime[GraphContext]) -> RunState:
    round_ = state["fix_round"] + 1
    ws.log(state["run_id"], "fix_phase_start", round=round_)
    _say(runtime, f"FIX (rodada {round_}/{MAX_FIX_ROUNDS}): angular_coder corrige os arquivos citados pelo ngc.")
    _invoke(
        runtime,
        state,
        f"fix_phase_{round_}",
        "FIX: `ngc --noEmit` falhou em /outputs/frontend. Agrupe os erros abaixo por arquivo e dispare task(angular_coder) "
        "para corrigir apenas os arquivos citados (tasks em paralelo quando os arquivos forem distintos). "
        "Responda com o que mudou.\n\n" + "\n".join(state["frontend_errors"]),
    )
    return {"fix_round": round_}


def after_verify(state: RunState) -> Literal["fix_phase", "deliver"]:
    if state["frontend_errors"] and state["fix_round"] < MAX_FIX_ROUNDS:
        return "fix_phase"
    return "deliver"


def deliver(state: RunState, runtime: Runtime[GraphContext]) -> RunState:
    """ng build (se ngc passou) e copia do projeto para a pasta de destino."""
    run_id = state["run_id"]
    frontend = ws.ROOT / ws.FRONTEND
    build_errors: list[str] = []
    if not state["frontend_errors"] and os.getenv("FRONTEND_CHECK", "1") == "1" and fc.available():
        _say(runtime, "DELIVER: ng build --configuration production.")
        build_errors = fc.build_frontend(frontend)
        ws.log(run_id, "frontend_build", ok=not build_errors, errors=build_errors)
    destination = Path(state.get("dest_dir") or ws.dest_dir())
    count = ws.deliver(destination)
    ws.log(run_id, "deliver", dest=str(destination), files=count)
    _say(runtime, f"   {count} arquivo(s) copiados para {destination}")
    _append_status(state["frontend_errors"], build_errors, destination)
    return {"build_errors": build_errors, "dest_dir": str(destination)}


def _append_status(ngc_errors: list[str], build_errors: list[str], destination: Path) -> None:
    readme = ws.ROOT / ws.FRONTEND / "README.md"
    body = readme.read_text(encoding="utf-8") if readme.exists() else "# Job Applier front-end\n"
    if ngc_errors:
        status = "`ngc --noEmit` ainda falha:\n\n```\n" + "\n".join(ngc_errors) + "\n```"
    elif build_errors:
        status = "`ngc --noEmit` passou; `ng build` falhou:\n\n```\n" + "\n".join(build_errors) + "\n```"
    else:
        status = "`ngc --noEmit` e `ng build --configuration production` passaram."
    readme.write_text(
        body.rstrip() + f"\n\n## Verificacao\n\n{status}\n\nEntregue em `{destination}`.\n", encoding="utf-8"
    )
    shutil.copy2(readme, destination / "README.md")


def compiled(state: RunState) -> bool:
    """Com integracao, vale a ultima checagem (frontend_build dentro de verify_integration); sem ela, ngc e ng build."""
    if state.get("project_dir"):
        return not state.get("integration_errors")
    return not state.get("frontend_errors") and not state.get("build_errors")


def finalize(state: RunState) -> RunState:
    run_id = state["run_id"]
    report = ws.usage_report(run_id)
    ok = compiled(state)
    ws.write_run_status(run_id, "done")
    run_dir = ws.snapshot_run(run_id, Path(state["input_path"]))
    ws.write_metadata(
        run_id,
        status="done",
        compiled=ok,
        fix_rounds=state.get("fix_round", 0),
        review_rounds=state.get("review_round", 0),
        **ratelimit.stats(),
        forced_build=state.get("forced_build", False),
        integration_errors=state.get("integration_errors", []),
        project_changes=state.get("project_changes", ""),
        files=ws.generated_files(),
        usage=report["totals"],
        phases=[
            {k: e.get(k) for k in ("event", "duration_s", "total_tokens", "parallel_task_calls")}
            for e in report["phases"]
        ],
        run_dir=str(run_dir),
    )
    ws.log(run_id, "finalize", run_dir=str(run_dir), compiled=ok, **report["totals"])
    return {"run_dir": str(run_dir)}


def after_deliver(state: RunState) -> Literal["integrate_phase", "finalize"]:
    return "integrate_phase" if state.get("project_dir") else "finalize"


def build_graph():
    from app.integrate import add_integration

    g = StateGraph(RunState, context_schema=GraphContext)
    for name, fn in [
        ("ingest", ingest),
        ("plan_phase", plan_phase),
        ("review_architecture", review_architecture),
        ("revise_architecture", revise_architecture),
        ("build_phase", build_phase),
        ("verify_frontend", verify_frontend),
        ("fix_phase", fix_phase),
        ("deliver", deliver),
        ("finalize", finalize),
    ]:
        g.add_node(name, fn)
    g.add_edge(START, "ingest")
    g.add_edge("ingest", "plan_phase")
    g.add_edge("plan_phase", "review_architecture")
    g.add_conditional_edges("review_architecture", after_review)
    g.add_edge("revise_architecture", "review_architecture")
    g.add_edge("build_phase", "verify_frontend")
    g.add_conditional_edges("verify_frontend", after_verify)
    g.add_edge("fix_phase", "verify_frontend")
    g.add_conditional_edges("deliver", after_deliver)
    add_integration(g, after=None)
    g.add_edge("finalize", END)
    return g.compile(checkpointer=ws.checkpointer())
