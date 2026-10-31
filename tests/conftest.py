"""Workspace temporario e sem checagem Angular por default: os testes rodam sem LLM e sem npm."""

import os
import shutil
from pathlib import Path

import pytest

SKILLS = Path(__file__).resolve().parent.parent / "workspace" / "skills"
PRIVACY = {"type": "object", "properties": {"consent_text": {"type": "string"}}, "required": ["consent_text"]}
FAKE_OPENAPI = {
    "openapi": "3.1.0",
    "info": {"title": "Fake", "version": "0"},
    "paths": {"/privacy": {"get": {"responses": {"200": {"content": {"application/json": {"schema": PRIVACY}}}}}}},
    "components": {"schemas": {"Privacy": PRIVACY}},
}


@pytest.fixture(autouse=True)
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("BUILDER_WORKSPACE", str(tmp_path / "ws"))
    monkeypatch.setenv("FRONTEND_CHECK", os.getenv("TEST_FRONTEND_CHECK", "0"))
    import app.workspace as ws

    monkeypatch.setattr(ws, "ROOT", tmp_path / "ws")
    monkeypatch.setattr(ws, "_saver", None)
    ws.ensure()
    shutil.copytree(SKILLS, ws.ROOT / "skills", dirs_exist_ok=True)
    import app.openapi

    monkeypatch.setattr(app.openapi, "fetch", lambda project_dir: FAKE_OPENAPI)  # sem uv run no projeto falso
    return ws.ROOT
