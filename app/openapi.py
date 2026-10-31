"""Schema OpenAPI do projeto alvo, sem subir servidor: importa a app FastAPI no venv do projeto e chama app.openapi().

OPENAPI_APP (default job_applier.main:app) diz qual app importar; PROJECT_CMD_PREFIX (ex.: UV_PROJECT_ENVIRONMENT=...)
antecede o comando; OPENAPI_URL, se definido, busca o schema de um servidor no ar em vez de importar.
"""

import json
import os
import shlex
import subprocess
import urllib.request
from pathlib import Path

SCRIPT = (
    "import json, importlib, os; m, a = os.environ['OPENAPI_APP'].split(':'); "
    "print(json.dumps(getattr(importlib.import_module(m), a).openapi()))"
)


def fetch(project_dir: Path) -> dict:
    """Schema OpenAPI (dict) do backend em project_dir; levanta RuntimeError com a saida do comando se falhar."""
    url = os.getenv("OPENAPI_URL")
    if url:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.load(r)
    cmd = f"{os.getenv('PROJECT_CMD_PREFIX', '')} TAVILY_API_KEY=dummy uv run python -c {shlex.quote(SCRIPT)}".strip()
    env = {**os.environ, "OPENAPI_APP": os.getenv("OPENAPI_APP", "job_applier.main:app")}
    r = subprocess.run(cmd, shell=True, cwd=project_dir, env=env, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[-2000:])
    return json.loads(r.stdout.strip().splitlines()[-1])
