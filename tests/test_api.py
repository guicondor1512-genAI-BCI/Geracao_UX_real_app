"""API HTTP: inicia uma run em background (launch falso), lista e devolve status, metadata e eventos."""

from fastapi.testclient import TestClient

from app import api
from app import workspace as ws


def fake_launch(args, notify=print, run_id=None):
    notify(f"> fake {args.command} {args.project}")
    ws.write_run_status(run_id, "running")
    ws.log(run_id, "ingest", mode=args.command)
    ws.write_metadata(run_id, mode=args.command, status="done", usage={"total_tokens": 1})
    ws.write_run_status(run_id, "done")
    return {"run_id": run_id}


def test_create_and_read_run(monkeypatch):
    monkeypatch.setattr(api.cli, "launch", fake_launch)
    api.RUNS.clear()
    client = TestClient(api.app)
    r = client.post("/runs", json={"mode": "describe", "project": "/proj"})
    assert r.status_code == 202
    run_id = r.json()["run_id"]
    api.RUNS[run_id]["thread"].join(timeout=5)
    run = client.get(f"/runs/{run_id}").json()
    assert run["status"] == "done" and run["metadata"]["mode"] == "describe" and run["notes"][0].startswith("> fake")
    assert client.get(f"/runs/{run_id}/events").json()[0]["event"] == "ingest"
    assert client.get("/runs").json()[0]["run_id"] == run_id
    assert client.get("/runs/nope").status_code == 404


def test_pending_run_blocks_without_force(monkeypatch):
    monkeypatch.setattr(api.cli, "launch", fake_launch)
    ws.write_run_status("run_old", "running")
    client = TestClient(api.app)
    assert client.post("/runs", json={"mode": "build", "project": "/proj"}).status_code == 409
    assert client.post("/runs", json={"mode": "build", "project": "/proj", "force": True}).status_code == 202


def test_cli_exit_becomes_failed_run(monkeypatch):
    def exiting(args, notify=print, run_id=None):
        raise SystemExit("Projeto nao encontrado: /nope")

    monkeypatch.setattr(api.cli, "launch", exiting)
    client = TestClient(api.app)
    run_id = client.post("/runs", json={"mode": "build", "project": "/nope"}).json()["run_id"]
    api.RUNS[run_id]["thread"].join(timeout=5)
    run = client.get(f"/runs/{run_id}").json()
    assert run["status"] == "failed" and "Projeto nao encontrado" in run["error"]
