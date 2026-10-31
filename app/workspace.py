"""Workspace do builder: pastas, run id, log jsonl, metadata e snapshot de cada run."""

import json
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

ROOT = Path(os.getenv("BUILDER_WORKSPACE", Path(__file__).resolve().parent.parent / "workspace"))
SUBDIRS = ["inputs", "current", "outputs", "logs", "metadata", "skills", "runs", "archive"]
FRONTEND = "outputs/frontend"


def dest_dir() -> Path:
    """Pasta onde o Angular final e gravado: FRONTEND_DEST ou ~/Codes/deepagents_jobapplier/frontend."""
    return Path(os.getenv("FRONTEND_DEST", "~/Codes/deepagents_jobapplier/frontend")).expanduser()


def ensure() -> Path:
    for d in SUBDIRS:
        (ROOT / d).mkdir(parents=True, exist_ok=True)
    return ROOT


def new_run_id() -> str:
    return datetime.now().strftime("run_%Y%m%d_%H%M%S")


_saver = None


def checkpointer() -> SqliteSaver:
    """SqliteSaver compartilhado pelo grafo e pelo deep agent (workspace/checkpoints.sqlite)."""
    global _saver
    if _saver is None:
        conn = sqlite3.connect(ROOT / "checkpoints.sqlite", check_same_thread=False)
        _saver = SqliteSaver(conn)
    return _saver


def write_run_status(run_id: str, status: str) -> None:
    """current/run.json com {run_id, thread_id, status} (running | failed | done)."""
    data = {
        "run_id": run_id,
        "thread_id": run_id,
        "status": status,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    (ROOT / "current" / "run.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def read_run_status() -> dict | None:
    f = ROOT / "current" / "run.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def write_metadata(run_id: str, **data) -> dict:
    """metadata/<run_id>.json: mescla os campos dados ao que ja existe e devolve o resultado."""
    path = ROOT / "metadata" / f"{run_id}.json"
    current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"run_id": run_id}
    current.update(data)
    current["updated_at"] = datetime.now().isoformat(timespec="seconds")
    path.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
    return current


def read_metadata(run_id: str) -> dict | None:
    path = ROOT / "metadata" / f"{run_id}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def list_run_ids() -> list[str]:
    return sorted(p.stem for p in (ROOT / "logs").glob("run_*.jsonl"))


def read_events(run_id: str) -> list[dict]:
    lines = (ROOT / "logs" / f"{run_id}.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def last_event(run_id: str) -> dict:
    events = read_events(run_id)
    return events[-1] if events else {}


USAGE_KEYS = ("duration_s", "input_tokens", "output_tokens", "total_tokens")


def usage_report(run_id: str) -> dict:
    """Agrega duracao e tokens dos eventos *_end do log: {"phases": [...], "totals": {...}}."""
    phases = [e for e in read_events(run_id) if e["event"].endswith("_end")]
    totals = {k: sum(e.get(k, 0) for e in phases) for k in USAGE_KEYS}
    totals["duration_s"] = round(totals["duration_s"], 1)
    return {"phases": phases, "totals": totals}


def log(run_id: str, event: str, **data) -> None:
    line = {"ts": datetime.now().isoformat(timespec="seconds"), "event": event, **data}
    with open(ROOT / "logs" / f"{run_id}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def _clear(name: str) -> None:
    """Esvazia workspace/<name>/ preservando .gitkeep."""
    for p in (ROOT / name).iterdir():
        if p.name == ".gitkeep":
            continue
        shutil.rmtree(p) if p.is_dir() else p.unlink()


def clear_current() -> None:
    _clear("current")


def clear_outputs() -> None:
    _clear("outputs")


def generated_files() -> list[str]:
    """Arquivos gerados em outputs/frontend/src, relativos a outputs/frontend."""
    root = ROOT / FRONTEND
    return sorted(str(p.relative_to(root)) for p in (root / "src").rglob("*") if p.is_file())


def snapshot_run(run_id: str, input_path: Path) -> Path:
    """Copia current, outputs (sem node_modules) e o log para runs/<id>; arquiva uma copia da spec."""
    dest = ROOT / "runs" / run_id
    ignore = shutil.ignore_patterns("node_modules", ".angular", "dist")
    for d in ("current", "outputs"):
        shutil.copytree(ROOT / d, dest / d, dirs_exist_ok=True, ignore=ignore)
    shutil.copy2(ROOT / "logs" / f"{run_id}.jsonl", dest / "log.jsonl")
    shutil.copy2(input_path, ROOT / "archive" / f"{run_id}__{input_path.name}")
    return dest


def deliver(destination: Path) -> int:
    """Copia outputs/frontend para a pasta de destino (substitui src/ e arquivos do projeto, preserva node_modules)."""
    src = ROOT / FRONTEND
    destination.mkdir(parents=True, exist_ok=True)
    if (destination / "src").exists():
        shutil.rmtree(destination / "src")
    ignore = shutil.ignore_patterns("node_modules", ".angular", "dist")
    shutil.copytree(src, destination, dirs_exist_ok=True, ignore=ignore)
    return sum(1 for p in destination.rglob("*") if p.is_file() and "node_modules" not in p.parts)
