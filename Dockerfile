# frontend-builder: deep agent (Python 3.12 + uv) com Node 22 para ngc/ng build do Angular gerado.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    BUILDER_WORKSPACE=/app/workspace \
    ANGULAR_CACHE=/opt/angular_cache \
    UX_RUNS_DIR=/ux/runs \
    UX_INPUTS_DIR=/ux/inputs \
    PROJECT_TEST_CMD="UV_PROJECT_ENVIRONMENT=/tmp/target-venv TAVILY_API_KEY=dummy uv run --with pytest pytest tests/ -q -x" \
    PROJECT_FORMAT_CMD="uvx black src tests" \
    PROJECT_CMD_PREFIX="UV_PROJECT_ENVIRONMENT=/tmp/target-venv"

# Node 22 (ngc, ng build), git (git status do projeto alvo) e uv.
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl git \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && git config --global --add safe.directory '*'
COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /uvx /bin/

WORKDIR /app

# Dependencias Python travadas (camada cacheada enquanto pyproject/uv.lock nao mudam).
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev

# Cache Angular: template + node_modules, fora do volume do workspace.
COPY app/templates/angular /opt/angular_cache
RUN cd /opt/angular_cache && npm install --no-audit --no-fund --loglevel=error

COPY app ./app
COPY workspace/skills ./workspace/skills
RUN mkdir -p workspace/inputs workspace/current workspace/outputs workspace/logs workspace/metadata workspace/runs workspace/archive

VOLUME ["/app/workspace"]
EXPOSE 8000
ENTRYPOINT ["/app/.venv/bin/python", "-m", "app.main"]
# Sem argumentos a imagem sobe a API em :8000; qualquer subcomando do CLI pode ser passado no lugar.
CMD ["serve"]
