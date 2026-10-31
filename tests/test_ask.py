"""POST /ask e run_agent com um agente falso; erro do agente vira 500."""

from fastapi.testclient import TestClient

from app import api
from app.ask import run_agent


class FakeMessage:
    def __init__(self, text):
        self.text = text


class FakeAskAgent:
    def __init__(self):
        self.questions = []

    def invoke(self, payload, config):
        self.questions.append(payload["messages"][0]["content"])
        return {"messages": [FakeMessage("A ultima run compilou (metadata/run_x.json).")]}


def test_run_agent_with_injected_agent():
    agent = FakeAskAgent()
    assert run_agent("A ultima run compilou?", agent=agent).startswith("A ultima run compilou")
    assert agent.questions == ["A ultima run compilou?"]


def test_ask_endpoint(monkeypatch, tmp_path):
    monkeypatch.setattr(api.qa, "run_agent", lambda q, p=None, agent=None: f"resposta para: {q} (projeto {p})")
    client = TestClient(api.app)
    r = client.post("/ask", json={"question": "quantas telas?", "project": str(tmp_path)})
    assert r.status_code == 200 and r.json()["response"].startswith("resposta para: quantas telas?")
    assert client.post("/ask", json={"question": "x", "project": "/nao/existe"}).status_code == 404


def test_ask_endpoint_agent_error_is_500(monkeypatch):
    def boom(q, p=None, agent=None):
        raise RuntimeError("provedor fora")

    monkeypatch.setattr(api.qa, "run_agent", boom)
    r = TestClient(api.app).post("/ask", json={"question": "x"})
    assert r.status_code == 500 and "provedor fora" in r.json()["detail"]
