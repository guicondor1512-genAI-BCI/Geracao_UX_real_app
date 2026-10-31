"""Acesso do agente a pasta do projeto alvo: ela aparece como /project/ no workspace virtual."""

import subprocess
from pathlib import Path

from deepagents.backends import CompositeBackend, FilesystemBackend

from app.workspace import ROOT

PROJECT_PREFIX = "/project/"


def backend(project_dir: Path | None):
    """FilesystemBackend do workspace; com project_dir, /project/ roteia para a pasta do projeto."""
    default = FilesystemBackend(root_dir=ROOT, virtual_mode=True)
    if project_dir is None:
        return default
    project = FilesystemBackend(root_dir=project_dir, virtual_mode=True)
    return CompositeBackend(default=default, routes={PROJECT_PREFIX: project})


def slug(project_dir: Path) -> str:
    return project_dir.name.replace("_", "-").lower()


def git_diff_stat(project_dir: Path) -> str:
    """`git status --short` do projeto (vazio se nao for repositorio git)."""
    r = subprocess.run(["git", "status", "--short"], cwd=project_dir, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""
