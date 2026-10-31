"""Checagem do Angular gerado: completa o projeto com o template, roda `ngc --noEmit` e, no fim, `ng build`.

As dependencias sao instaladas uma vez em workspace/.angular_cache (template + node_modules); a cada checagem o src/
gerado e copiado para la e compilado com strictTemplates.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

from app import workspace as ws

TEMPLATE = Path(__file__).resolve().parent / "templates" / "angular"
TEMPLATE_FILES = (
    "package.json",
    "angular.json",
    "tsconfig.json",
    "tsconfig.app.json",
    ".gitignore",
    "src/main.ts",
    "src/index.html",
    "src/styles.css",
    "src/environments/environment.ts",
    "src/app/app.config.ts",
)
MAX_LINES = 80
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def available() -> bool:
    return shutil.which("npm") is not None


def scaffold(frontend_dir: Path) -> None:
    """Copia para outputs/frontend os arquivos do template que ainda nao existem (idempotente)."""
    for rel in TEMPLATE_FILES:
        dst = frontend_dir / rel
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(TEMPLATE / rel, dst)


def cache_dir() -> Path:
    """ANGULAR_CACHE ou workspace/.angular_cache (na imagem Docker fica fora do volume do workspace)."""
    return Path(os.getenv("ANGULAR_CACHE", ws.ROOT / ".angular_cache"))


def ensure_cache() -> Path:
    """Template sempre sincronizado; node_modules instalado so na primeira vez."""
    cache = cache_dir()
    shutil.copytree(TEMPLATE, cache, dirs_exist_ok=True)
    if not (cache / "node_modules").exists():
        subprocess.run(
            ["npm", "install", "--no-audit", "--no-fund", "--loglevel=error"],
            cwd=cache,
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
    return cache


def _sync_src(frontend_dir: Path) -> Path:
    cache = ensure_cache()
    shutil.rmtree(cache / "src", ignore_errors=True)
    shutil.copytree(frontend_dir / "src", cache / "src")
    return cache


def _error_lines(r: subprocess.CompletedProcess) -> list[str]:
    if r.returncode == 0:
        return []
    lines = [ANSI.sub("", line).rstrip() for line in (r.stdout + r.stderr).splitlines() if line.strip()]
    return lines[:MAX_LINES]


def check_frontend(frontend_dir: Path) -> list[str]:
    """ngc --noEmit sobre o src/ gerado. Lista vazia = compila; senao as linhas de erro do compilador."""
    scaffold(frontend_dir)
    cache = _sync_src(frontend_dir)
    ngc = str(cache / "node_modules" / ".bin" / "ngc")
    r = subprocess.run(
        [ngc, "-p", "tsconfig.app.json", "--noEmit", "--pretty", "false"],
        cwd=cache,
        capture_output=True,
        text=True,
        timeout=300,
    )
    return _error_lines(r)


def build_frontend(frontend_dir: Path) -> list[str]:
    """ng build (producao) sobre o src/ gerado. Lista vazia = bundle ok; senao as linhas de erro."""
    cache = _sync_src(frontend_dir)
    ng = str(cache / "node_modules" / ".bin" / "ng")
    r = subprocess.run(
        [ng, "build", "--configuration", "production"],
        cwd=cache,
        capture_output=True,
        text=True,
        timeout=600,
    )
    return _error_lines(r)
