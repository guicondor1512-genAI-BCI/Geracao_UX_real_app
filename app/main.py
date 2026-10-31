"""CLI do builder:
  python -m app.main describe --project DIR [--to-ux]          le o backend e gera o .md para o designer
  python -m app.main build --latest-ux-run [--project DIR]      Angular a partir da run mais recente do ux-deep-agents
  python -m app.main build --ux-run RUN_DIR [--project DIR]     idem, run especifica
  python -m app.main build SPEC.md [--screens J] [--reference D] [--project DIR] [--dest DIR]
  python -m app.main integrate --project DIR [--dest DIR]       so a integracao, sobre um front-end ja entregue
  python -m app.main list | resume [RUN_ID]
Com --project, o Angular final vai para <projeto>/frontend e a fase de integracao adapta back e front.
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from app import workspace as ws
from app.agent import build_agent
from app.describe import build_describe_graph
from app.graph import GraphContext, build_graph
from app.integrate import build_integrate_graph

UX_RUNS_DIR = Path(os.getenv("UX_RUNS_DIR", "~/UX Project/ux-deep-agents/workspace/runs")).expanduser()


def ux_run_inputs(run_dir: Path) -> dict:
    """Entradas do builder a partir de um snapshot de run do ux-deep-agents."""
    spec = run_dir / "outputs" / "prototypes" / "screens.md"
    if not spec.exists():
        sys.exit(f"{spec} nao existe: a run do ux-deep-agents nao gerou o prototipo front-end.")
    screens = run_dir / "current" / "screens.json"
    reference = run_dir / "outputs" / "frontend"
    stitch = next((d for d in sorted((run_dir / "outputs" / "stitch").glob("*/")) if any(d.glob("*.html"))), None)
    return {
        "input_path": str(spec),
        "screens_path": str(screens) if screens.exists() else None,
        "reference_dir": str(reference) if (reference / "src").exists() else None,
        "stitch_dir": str(stitch) if stitch else None,
    }


def latest_ux_run() -> Path:
    runs = sorted(p for p in UX_RUNS_DIR.glob("run_*") if p.is_dir())
    if not runs:
        sys.exit(f"Nenhuma run em {UX_RUNS_DIR}")
    return runs[-1]


def project_of(args: argparse.Namespace) -> Path | None:
    if not getattr(args, "project", None):
        return None
    project = Path(args.project).expanduser().resolve()
    if not project.is_dir():
        sys.exit(f"Projeto nao encontrado: {project}")
    return project


def dest_of(args: argparse.Namespace, project: Path | None) -> str:
    if args.dest:
        return str(Path(args.dest).expanduser().resolve())
    return str(project / "frontend") if project else str(ws.dest_dir())


def build_inputs(args: argparse.Namespace) -> dict:
    if args.ux_run:
        inputs = ux_run_inputs(Path(args.ux_run).expanduser())
    elif args.latest_ux_run:
        inputs = ux_run_inputs(latest_ux_run())
    else:
        spec = Path(args.spec) if args.spec else next(iter(sorted((ws.ROOT / "inputs").glob("*.md"))), None)
        if spec is None:
            sys.exit("Nenhuma spec .md em workspace/inputs/")
        inputs = {
            "input_path": str(spec),
            "screens_path": args.screens,
            "reference_dir": args.reference,
            "stitch_dir": args.stitch,
        }
    project = project_of(args)
    inputs["project_dir"] = str(project) if project else None
    inputs["dest_dir"] = dest_of(args, project)
    return {k: v for k, v in inputs.items() if v}


def guard_pending(force: bool) -> None:
    pending = ws.read_run_status()
    if pending and pending["status"] != "done" and not force:
        sys.exit(f"Run {pending['run_id']} esta '{pending['status']}'. Use resume, list ou --force.")


def start(graph, project: Path | None, state: dict, label: str) -> dict:
    run_id = ws.new_run_id()
    print(f"> {label} (run {run_id})")
    context = GraphContext(agent=build_agent(project), notify=print)
    return graph.invoke({**state, "run_id": run_id}, config={"configurable": {"thread_id": run_id}}, context=context)


def resume(run_id: str) -> dict:
    """Retoma o grafo do modo registrado em metadata/<run_id>.json."""
    meta = ws.write_metadata(run_id)
    graph = {"describe": build_describe_graph(), "integrate": build_integrate_graph()}.get(
        meta.get("mode"), build_graph()
    )
    config = {"configurable": {"thread_id": run_id}}
    snap = graph.get_state(config)
    if not snap.next:
        sys.exit(f"Run {run_id} nao tem etapa pendente (concluida ou inexistente).")
    print(f"> Retomando {run_id} em {', '.join(snap.next)}")
    project = Path(meta["project"]) if meta.get("project") else None
    return graph.invoke(None, config=config, context=GraphContext(agent=build_agent(project), notify=print))


def list_runs() -> None:
    graph = build_graph()
    for run_id in ws.list_run_ids():
        ev = ws.last_event(run_id)
        if ev.get("event") == "failed":
            status = f"failed ({ev.get('error_type')}: {ev.get('error', '')[:80]})"
        else:
            snap = graph.get_state({"configurable": {"thread_id": run_id}})
            status = f"interrupted em {', '.join(snap.next)}" if snap.next else "done"
        t = ws.usage_report(run_id)["totals"]
        print(f"{run_id}  {status}  [{t['duration_s']}s, {t['total_tokens']} tokens]")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m app.main")
    sub = parser.add_subparsers(dest="command", required=True)
    d = sub.add_parser("describe", help="gera o .md do fluxo do backend para o designer")
    d.add_argument("--project", required=True, help="pasta do projeto (backend)")
    d.add_argument("--to-ux", action="store_true", help="copia o .md tambem para UX_INPUTS_DIR (ux-deep-agents)")
    d.add_argument("--force", action="store_true")
    b = sub.add_parser("build", help="gera o Angular a partir do prototipo front-end")
    b.add_argument("spec", nargs="?", help="spec .md (default: primeiro .md em workspace/inputs)")
    b.add_argument("--screens")
    b.add_argument("--reference")
    b.add_argument("--stitch", help="pasta com os HTML das telas aprovadas no Stitch (fonte visual)")
    b.add_argument("--ux-run", metavar="RUN_DIR")
    b.add_argument("--latest-ux-run", action="store_true")
    b.add_argument("--project", help="pasta do projeto: destino <projeto>/frontend + fase de integracao")
    b.add_argument("--dest")
    b.add_argument("--force", action="store_true")
    i = sub.add_parser("integrate", help="integra um front-end ja entregue ao backend do projeto")
    i.add_argument("--project", required=True)
    i.add_argument("--dest", help="pasta do front-end (default: <projeto>/frontend)")
    i.add_argument("--force", action="store_true")
    r = sub.add_parser("resume")
    r.add_argument("run_id", nargs="?")
    sub.add_parser("list")
    return parser.parse_args(argv)


def report(result: dict) -> None:
    totals = ws.usage_report(result["run_id"])["totals"]
    errors = result.get("frontend_errors") or result.get("build_errors") or result.get("integration_errors")
    status = "COM ERROS" if errors else "ok"
    print(f"\nRun {result['run_id']}: {totals['duration_s']}s, {totals['total_tokens']} tokens; {status}.")
    for key, label in (("brief_path", "Brief"), ("dest_dir", "Front-end em"), ("run_dir", "Snapshot")):
        if result.get(key):
            print(f"  {label}: {result[key]}")
    if result.get("project_changes"):
        print("  Mudancas no projeto (git status):\n    " + result["project_changes"].replace("\n", "\n    "))
    print("\n" + result.get("final_message", ""))


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    ws.ensure()
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "list":
        return list_runs()
    if args.command == "resume":
        run_id = args.run_id or (ws.read_run_status() or {}).get("run_id")
        if not run_id:
            sys.exit("Nenhuma run para retomar: informe o RUN_ID")
        return report(resume(run_id))
    guard_pending(args.force)
    if args.command == "describe":
        project = project_of(args)
        state = {"project_dir": str(project), "to_ux": args.to_ux}
        return report(start(build_describe_graph(), project, state, f"Descrevendo {project}"))
    if args.command == "integrate":
        project = project_of(args)
        state = {"project_dir": str(project), "dest_dir": dest_of(args, project)}
        return report(start(build_integrate_graph(), project, state, f"Integrando {state['dest_dir']} a {project}"))
    inputs = build_inputs(args)
    report(start(build_graph(), project_of(args), inputs, f"Construindo a partir de {inputs['input_path']}"))


if __name__ == "__main__":
    main()
