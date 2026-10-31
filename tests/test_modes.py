"""describe, build --project (com integracao) e integrate, com agente falso e checagens triviais."""

import json
from pathlib import Path

import pytest

from app import workspace as ws
from app.describe import build_describe_graph
from app.graph import GraphContext, build_graph
from app.integrate import build_integrate_graph
from app.tools import project_check as pc
from tests.test_graph import SPEC, FakeAgent, FakeMessage


@pytest.fixture
def project(tmp_path, monkeypatch) -> Path:
    proj = tmp_path / "proj"
    (proj / "src" / "pkg").mkdir(parents=True)
    (proj / "src" / "pkg" / "main.py").write_text("app = None\n")
    monkeypatch.setattr(pc, "TEST_CMD", "true")
    monkeypatch.setattr(pc, "FORMAT_CMD", "true")
    return proj


class ProjectAgent(FakeAgent):
    def invoke(self, payload, config):
        text = payload["messages"][0]["content"]
        if text.startswith("DESCRIBE"):
            self.phases.append("DESCRIBE")
            (ws.ROOT / "outputs" / "brief" / "proj-descricao.md").write_text("# Proj\n## 1. O que e\n")
            return {"messages": [FakeMessage("brief ok")]}
        if text.startswith("INTEGRATE"):
            self.phases.append("INTEGRATE")
            return {"messages": [FakeMessage("integrado")]}
        return super().invoke(payload, config)


def test_describe(project):
    agent = ProjectAgent()
    result = build_describe_graph().invoke(
        {"project_dir": str(project), "run_id": "run_d"},
        config={"configurable": {"thread_id": "run_d"}},
        context=GraphContext(agent=agent),
    )
    assert agent.phases == ["DESCRIBE"]
    assert Path(result["brief_path"]).name == "proj-descricao.md"
    assert (ws.ROOT / "inputs" / "proj-descricao.md").exists()
    assert json.loads((ws.ROOT / "metadata" / "run_d.json").read_text())["mode"] == "describe"


def test_build_with_project_runs_integration(project, tmp_path):
    spec = tmp_path / "screens.md"
    spec.write_text(SPEC)
    agent = ProjectAgent()
    result = build_graph().invoke(
        {
            "input_path": str(spec),
            "run_id": "run_b",
            "project_dir": str(project),
            "dest_dir": str(project / "frontend"),
        },
        config={"configurable": {"thread_id": "run_b"}},
        context=GraphContext(agent=agent),
    )
    assert agent.phases == ["PLANO", "BUILD", "INTEGRATE"]
    assert result["integration_errors"] == []
    assert json.loads((ws.ROOT / "metadata" / "run_b.json").read_text())["compiled"] is True
    assert (project / "frontend" / "src" / "app" / "app.ts").exists()
    events = [e["event"] for e in ws.read_events("run_b")]
    assert events.count("integration_check") == 3 and events[-1] == "finalize"


def test_integrate_only(project, monkeypatch):
    (project / "frontend" / "src").mkdir(parents=True)
    (project / "frontend" / "README.md").write_text("# fe\n")
    monkeypatch.setattr(pc, "TEST_CMD", "false")  # testes do backend falham: uma rodada de correcao
    agent = ProjectAgent()
    result = build_integrate_graph().invoke(
        {"project_dir": str(project), "dest_dir": str(project / "frontend"), "run_id": "run_i"},
        config={"configurable": {"thread_id": "run_i"}},
        context=GraphContext(agent=agent),
    )
    assert agent.phases == ["INTEGRATE", "INTEGRATE"]
    assert len(result["integration_errors"]) == 1 and result["integration_errors"][0].startswith("## tests")
    assert json.loads((ws.ROOT / "metadata" / "run_i.json").read_text())["compiled"] is False


def test_compiled_uses_integration_result_when_project_given():
    from app.graph import compiled

    state = {"project_dir": "/p", "frontend_errors": ["erro antes da integracao"], "integration_errors": []}
    assert compiled(state) is True
    assert compiled({"frontend_errors": ["x"]}) is False
    assert compiled({"project_dir": "/p", "integration_errors": ["## tests\nfalhou"]}) is False
