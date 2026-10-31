"""API HTTP do builder: inicia describe | build | integrate em background e expoe status, metadata e eventos.

POST /runs            {mode, project, to_ux?, ux_run?, dest?, force?} -> 202 {run_id}
GET  /runs            runs conhecidas, mais recente primeiro, com status e uso
GET  /runs/{run_id}   metadata + notas de progresso (+ erro, se falhou)
GET  /runs/{run_id}/events   eventos do log jsonl
POST /ask             {question, project?} -> {response}: pergunta ao agente (so leitura) sobre runs e projeto
POST /runs/{run_id}/decision {approved, feedback?}  retoma uma run `paused` na revisao da arquitetura (D3)
"""

import threading
from argparse import Namespace
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app import ask as qa
from app import main as cli
from app import workspace as ws

app = FastAPI(title="frontend-builder", description="Deep agent que gera o brief, o Angular e a integracao.")
RUNS: dict[str, dict] = {}


class NewRun(BaseModel):
    mode: Literal["describe", "build", "integrate"]
    project: str
    to_ux: bool = False
    ux_run: str | None = None
    """Snapshot de run do ux-deep-agents (build); sem ele, a run mais recente de UX_RUNS_DIR."""
    dest: str | None = None
    force: bool = False
    auto_approve: bool = False
    """true pula a revisao humana da arquitetura; false deixa a run `paused` ate POST /runs/{id}/decision."""


def namespace(body: NewRun) -> Namespace:
    return Namespace(
        command=body.mode,
        project=body.project,
        to_ux=body.to_ux,
        ux_run=body.ux_run,
        latest_ux_run=body.ux_run is None,
        spec=None,
        screens=None,
        reference=None,
        stitch=None,
        dest=body.dest,
        force=body.force,
        auto_approve=body.auto_approve,
    )


def _finish(entry: dict, result: dict) -> None:
    """Resultado de um invoke: run pausada (payload da revisao) ou concluida."""
    if "__interrupt__" in result:
        entry["review"] = result["__interrupt__"][0].value
    else:
        entry["review"] = None
        entry["result"] = result


def work(run_id: str, args: Namespace) -> None:
    entry = RUNS[run_id]
    try:
        _finish(entry, cli.launch(args, notify=entry["notes"].append, run_id=run_id))
    except (Exception, SystemExit) as e:  # sys.exit do CLI (projeto inexistente, spec ausente) vira erro da run
        entry["error"] = f"{type(e).__name__}: {e}"[:2000]


def decide(run_id: str, decision: dict) -> None:
    entry = RUNS[run_id]
    try:
        _finish(entry, cli.continue_run(run_id, decision, notify=entry["notes"].append))
    except (Exception, SystemExit) as e:
        entry["error"] = f"{type(e).__name__}: {e}"[:2000]


@app.post("/runs", status_code=202)
def create_run(body: NewRun) -> dict:
    ws.ensure()
    pending = ws.read_run_status()
    if pending and pending["status"] in ("running", "paused") and not body.force:
        raise HTTPException(409, f"Run {pending['run_id']} esta '{pending['status']}'; use force para iniciar outra.")
    run_id = ws.new_run_id()
    RUNS[run_id] = {"notes": [], "result": None, "error": None, "review": None}
    thread = threading.Thread(target=work, args=(run_id, namespace(body)), daemon=True, name=run_id)
    RUNS[run_id]["thread"] = thread
    thread.start()
    return {"run_id": run_id, "mode": body.mode}


def status_of(run_id: str) -> str:
    entry = RUNS.get(run_id)
    if entry and entry["error"]:
        return "failed"
    if entry and entry["thread"].is_alive():
        return "running"
    if entry and entry.get("review"):
        return "paused"
    meta = ws.read_metadata(run_id)
    return meta.get("status", "unknown") if meta else "unknown"


@app.get("/runs")
def list_runs() -> list[dict]:
    ws.ensure()
    out = []
    for run_id in sorted(ws.list_run_ids(), reverse=True):
        meta = ws.read_metadata(run_id) or {}
        out.append(
            {
                "run_id": run_id,
                "mode": meta.get("mode", "build"),
                "status": status_of(run_id),
                "usage": meta.get("usage"),
            }
        )
    return out


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    meta = ws.read_metadata(run_id)
    entry = RUNS.get(run_id)
    if meta is None and entry is None:
        raise HTTPException(404, "run desconhecida")
    return {
        "run_id": run_id,
        "status": status_of(run_id),
        "metadata": meta,
        "notes": entry["notes"] if entry else [],
        "error": entry["error"] if entry else None,
        "review": entry.get("review") if entry else None,
    }


class Decision(BaseModel):
    approved: bool
    feedback: str = ""


@app.post("/runs/{run_id}/decision", status_code=202)
def post_decision(run_id: str, body: Decision) -> dict:
    """Aprova a arquitetura ou devolve feedback; a run `paused` volta a rodar em background."""
    entry = RUNS.get(run_id)
    if entry is None:
        raise HTTPException(404, "run desconhecida")
    if entry["thread"].is_alive() or not entry.get("review"):
        raise HTTPException(409, "a run nao esta pausada aguardando revisao")
    entry["review"] = None
    thread = threading.Thread(target=decide, args=(run_id, body.model_dump()), daemon=True, name=run_id)
    entry["thread"] = thread
    thread.start()
    return {"run_id": run_id, "status": "running"}


@app.get("/runs/{run_id}/events")
def get_events(run_id: str) -> list[dict]:
    if not (ws.ROOT / "logs" / f"{run_id}.jsonl").exists():
        raise HTTPException(404, "run sem log")
    return ws.read_events(run_id)


class Query(BaseModel):
    question: str
    project: str | None = None
    """Pasta do projeto alvo a montar em /project/ (opcional)."""


@app.post("/ask")
def ask(query: Query) -> dict:
    """Responde uma pergunta sobre as runs, o workspace e o projeto alvo, com o deep agent em modo so leitura."""
    project = Path(query.project).expanduser().resolve() if query.project else None
    if project and not project.is_dir():
        raise HTTPException(404, f"Projeto nao encontrado: {project}")
    try:
        return {"response": qa.run_agent(query.question, project)}
    except Exception as e:
        raise HTTPException(500, f"{type(e).__name__}: {e}"[:500])


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
