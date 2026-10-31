"""Workspace temporario e sem checagem Angular por default: os testes rodam sem LLM e sem npm."""

import os
import shutil
from pathlib import Path

import pytest

SKILLS = Path(__file__).resolve().parent.parent / "workspace" / "skills"


@pytest.fixture(autouse=True)
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("BUILDER_WORKSPACE", str(tmp_path / "ws"))
    monkeypatch.setenv("FRONTEND_CHECK", os.getenv("TEST_FRONTEND_CHECK", "0"))
    import app.workspace as ws

    monkeypatch.setattr(ws, "ROOT", tmp_path / "ws")
    monkeypatch.setattr(ws, "_saver", None)
    ws.ensure()
    shutil.copytree(SKILLS, ws.ROOT / "skills", dirs_exist_ok=True)
    return ws.ROOT
