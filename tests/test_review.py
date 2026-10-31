"""Revisao humana da arquitetura (D3): pausa apos o plano, revisao com feedback, aprovacao e limite de rodadas."""

import json
from pathlib import Path

from fastapi.testclient import TestClient
from langgraph.types import Command

from app import api
from app import graph as G
from app import workspace as ws
from app.graph import GraphContext, build_graph
from tests.test_graph import SPEC, FakeAgent


def _start(tmp_path: Path, run_id: str, agent: FakeAgent):
    spec = tmp_path / "screens.md"
    spec.write_text(SPEC)
    (ws.ROOT / "current").mkdir(exist_ok=True)
    graph = build_graph()
    config = {"configurable": {"thread_id": run_id}}
    ctx = GraphContext(agent=agent)
    result = graph.invoke(
        {"input_path": str(spec), "run_id": run_id, "dest_dir": str(tmp_path / "dest")}, config=config, context=ctx
    )
    return graph, config, ctx, result


def test_pauses_after_plan_and_resumes_on_approval(tmp_path: Path):
    agent = FakeAgent()
    graph, config, ctx, result = _start(tmp_path, "run_r1", agent)
    payload = result["__interrupt__"][0].value
    assert agent.phases == ["PLANO"] and payload["round"] == 1
    assert "home" in payload["architecture"] and ws.read_run_status()["status"] == "paused"
    result = graph.invoke(Command(resume={"approved": True, "feedback": ""}), config=config, context=ctx)
    assert agent.phases == ["PLANO", "BUILD"] and result["run_dir"]
    meta = json.loads((ws.ROOT / "metadata" / "run_r1.json").read_text())
    assert meta["status"] == "done" and meta["review_rounds"] == 1 and meta["forced_build"] is False


def test_rejection_revises_and_persists_feedback(tmp_path: Path):
    agent = FakeAgent()
    graph, config, ctx, result = _start(tmp_path, "run_r2", agent)
    result = graph.invoke(
        Command(resume={"approved": False, "feedback": "Junte search e review num lote"}), config=config, context=ctx
    )
    assert agent.phases == ["PLANO", "REVISAO"] and result["__interrupt__"][0].value["round"] == 2
    assert "Junte search e review" in (ws.ROOT / "current" / "feedback.md").read_text()
    result = graph.invoke(Command(resume={"approved": True}), config=config, context=ctx)
    assert agent.phases == ["PLANO", "REVISAO", "BUILD"] and result["run_dir"]
    events = [e["event"] for e in ws.read_events("run_r2")]
    assert events.count("review_architecture") == 2 and "revise_start" in events


def test_forced_build_after_max_rounds(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(G, "MAX_REVIEW_ROUNDS", 1)
    agent = FakeAgent()
    graph, config, ctx, result = _start(tmp_path, "run_r3", agent)
    result = graph.invoke(Command(resume={"approved": False, "feedback": ""}), config=config, context=ctx)
    assert agent.phases == ["PLANO", "BUILD"] and result["forced_build"] is True
    assert "Reprovado sem comentario." in (ws.ROOT / "current" / "feedback.md").read_text()
    assert "forced_build" in [e["event"] for e in ws.read_events("run_r3")]


class Paused:
    def __init__(self, value):
        self.value = value


def test_api_pause_and_decision(monkeypatch):
    def launch(args, notify=print, run_id=None, decide=None):
        ws.write_run_status(run_id, "paused")
        ws.write_metadata(run_id, mode="build", status="paused")
        return {"__interrupt__": [Paused({"round": 1, "architecture": "| home | /home |"})]}

    def continue_run(run_id, decision, notify=print, decide=None):
        assert decision == {"approved": True, "feedback": "ok"}
        ws.write_metadata(run_id, status="done")
        ws.write_run_status(run_id, "done")
        return {"run_id": run_id}

    monkeypatch.setattr(api.cli, "launch", launch)
    monkeypatch.setattr(api.cli, "continue_run", continue_run)
    api.RUNS.clear()
    client = TestClient(api.app)
    run_id = client.post("/runs", json={"mode": "build", "project": "/p"}).json()["run_id"]
    api.RUNS[run_id]["thread"].join(timeout=5)
    run = client.get(f"/runs/{run_id}").json()
    assert run["status"] == "paused" and run["review"]["round"] == 1
    assert client.post(f"/runs/{run_id}/decision", json={"approved": True, "feedback": "ok"}).status_code == 202
    api.RUNS[run_id]["thread"].join(timeout=5)
    assert client.get(f"/runs/{run_id}").json()["status"] == "done"
    assert client.post(f"/runs/{run_id}/decision", json={"approved": True}).status_code == 409
