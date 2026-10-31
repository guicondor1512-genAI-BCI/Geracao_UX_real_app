"""project_check: roda as verificacoes do projeto alvo (testes do backend, formatacao, build do front-end).

Os comandos sao os do Job Applier por default; PROJECT_TEST_CMD e PROJECT_FORMAT_CMD sobrescrevem.
"""

import os
import subprocess
from pathlib import Path
from typing import Literal

from langchain_core.tools import tool

from app import frontend_check as fc

MAX_CHARS = 6000
TEST_CMD = os.getenv("PROJECT_TEST_CMD", "TAVILY_API_KEY=dummy uv run --with pytest pytest tests/ -q -x")
FORMAT_CMD = os.getenv("PROJECT_FORMAT_CMD", "uvx black src tests")
Kind = Literal["tests", "format", "frontend_build"]

_project_dir: Path | None = None
_frontend_dir: Path | None = None


def configure(project_dir: Path, frontend_dir: Path) -> None:
    global _project_dir, _frontend_dir
    _project_dir, _frontend_dir = project_dir, frontend_dir


def run_check(kind: Kind) -> tuple[bool, str]:
    """(ok, saida) de uma verificacao. frontend_build = ngc --noEmit + ng build sobre a pasta do front-end."""
    assert _project_dir and _frontend_dir
    if kind == "frontend_build":
        if os.getenv("FRONTEND_CHECK", "1") != "1" or not fc.available():
            return (True, "frontend_build pulado (FRONTEND_CHECK=0 ou npm ausente).")
        errors = fc.check_frontend(_frontend_dir) or fc.build_frontend(_frontend_dir)
        return (not errors, "\n".join(errors) or "ngc e ng build passaram.")
    cmd = TEST_CMD if kind == "tests" else FORMAT_CMD
    r = subprocess.run(cmd, shell=True, cwd=_project_dir, capture_output=True, text=True, timeout=900)
    out = (r.stdout + r.stderr).strip()
    return (r.returncode == 0, out[-MAX_CHARS:] or f"exit {r.returncode}")


@tool
def project_check(kind: Kind) -> str:
    """Roda uma verificacao no projeto alvo e devolve a saida: 'tests' (testes do backend), 'format' (formata o
    codigo Python com black) ou 'frontend_build' (ngc --noEmit + ng build do front-end Angular). Chame apos editar."""
    ok, out = run_check(kind)
    return f"{kind}: {'OK' if ok else 'FALHOU'}\n{out}"
