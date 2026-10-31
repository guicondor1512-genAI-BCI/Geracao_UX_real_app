# frontend-builder

Deep Agent (LangChain `deepagents`) orquestrado por **LangGraph** com três comandos sobre um projeto alvo (`--project DIR`):

1. `describe`: lê o backend do projeto e gera o `.md` que explica o produto e seus fluxos para um designer prototipar as
   telas (entrada do microserviço `ux-deep-agents`, via "choose file" da interface web dele).
2. `build`: constrói a aplicação **Angular 22** a partir do protótipo front-end que o `ux-deep-agents` gerou:
   `outputs/prototypes/screens.md` + `screens.json` (o que cada tela faz) e os **HTML das telas aprovadas no Stitch**
   (`outputs/stitch/<slug>/<id>.html`, a fonte visual: layout, classes Tailwind, tema de cores e fontes). Grava em
   `<projeto>/frontend/` e, com `--project`, segue para a integração.
3. `integrate`: adapta backend e front-end para funcionarem juntos (CORS, servir o build, `environment.ts`, contrato da
   API, README) e roda as checagens do projeto (black, pytest, `ngc` + `ng build`).

Todos os agentes usam `openai:gpt-6-luna` (`app/models.py`; `MODEL_<AGENTE>` sobrescreve).

## Pipeline

```
describe:  ingest_project -> describe_phase (backend_analyst) -> finalize_describe
build:     ingest -> plan_phase -> build_phase -> verify_frontend --(erros, ate MAX_FIX_ROUNDS)--> fix_phase -> verify_frontend
                                            '--(ok)--> deliver (ng build + copia) -> [integrate_phase -> verify_integration] -> finalize
integrate: ingest_integrate -> integrate_phase (integrator) -> verify_integration --(erros, 1 rodada)--> integrate_fix -> finalize
```

| Fase | Quem | O que faz |
|---|---|---|
| `ingest` | pipeline | copia spec, `screens.json`, `current/stitch/<id>.html` e injeta a config Tailwind do Stitch (tema, fontes, plugins) em `src/index.html` (`app/theme.py`) |
| `plan_phase` | orquestrador -> `architect` | `current/plan.md`, `current/architecture.md` (tela -> rota -> arquivo, design tokens e layout do Stitch, shared, modelos, serviços), núcleo do app (`app.ts`, `app.routes.ts`, `core/**`, `shared/**`) |
| `build_phase` | orquestrador -> N x `angular_coder` em paralelo | um lote de telas por `task()`; cada tela converte o HTML do Stitch em `src/app/screens/<id>/<id>.ts` (estrutura e classes preservadas, conteúdo vira signals e `@for`, estados loading/vazio/erro); depois `README.md` |
| `verify_frontend` | pipeline | `ngc --noEmit` (strictTemplates) em `workspace/.angular_cache` |
| `fix_phase` | orquestrador -> `angular_coder` | corrige só os arquivos citados pelo `ngc` |
| `deliver` | pipeline | `ng build --configuration production` e cópia para `<projeto>/frontend` (ou `FRONTEND_DEST`) |
| `integrate_phase` | orquestrador -> `integrator` | CORS e `/app` no FastAPI, `useMocks: false`, contrato do front-end = backend, README; `project_check` até passar |
| `verify_integration` | pipeline | `uvx black`, `pytest` do backend e `ngc` + `ng build` (`PROJECT_TEST_CMD`/`PROJECT_FORMAT_CMD` sobrescrevem) |
| `describe_phase` | orquestrador -> `backend_analyst` | `outputs/brief/<slug>-descricao.md` com as 10 seções da skill `ux-brief`; cópia em `inputs/` e, com `--to-ux`, em `UX_INPUTS_DIR` |
| `finalize` | pipeline | snapshot em `runs/<run_id>/`, `metadata/<run_id>.json` (inclui `git status` do projeto), spec arquivada |

O projeto alvo aparece para os agentes como `/project/` (`CompositeBackend`); o workspace continua em `/`.

O projeto Angular base (package.json, angular.json, tsconfig, main.ts, index.html com Tailwind via CDN,
`environments/environment.ts` com `apiBaseUrl`/`useMocks`, `app.config.ts` com HttpClient e Router) vem de
`app/templates/angular/`; os agentes geram só `src/app/**` e `README.md`. O app roda sem backend (`useMocks: true`)
com `MockJobApplierApi`; `HttpJobApplierApi` segue o contrato da skill `jobapplier-api`.

## Workspace

| Pasta | Uso |
|---|---|
| `workspace/inputs/` | specs `.md` a processar (ou use `--ux-run` / `--latest-ux-run`) |
| `workspace/current/` | run atual: `spec.md`, `screens.json`, `stitch/` (HTML aprovado por tela), `reference/` (protótipo anterior, opcional), `plan.md`, `architecture.md`, `run.json` |
| `workspace/outputs/frontend/` | projeto Angular gerado (limpo a cada run) |
| `workspace/logs/` | `<run_id>.jsonl`: eventos, duração e tokens por fase, erros do `ngc` |
| `workspace/metadata/` | `<run_id>.json`: entradas, status, arquivos gerados, uso, destino |
| `workspace/skills/` | `angular-app`, `jobapplier-api`, `ux-brief`, `integration` (SKILL.md lidos pelos subagents) |
| `workspace/runs/` | snapshot imutável de cada run |
| `workspace/archive/` | cópia da spec processada |
| `workspace/.angular_cache/` | template + `node_modules` para `ngc`/`ng build` |

## Versionamento de runs

![Versionamento de runs](docs/versionamento_runs.jpeg)

Cada execução recebe um `run_id` (`run_YYYYMMDD_HHMMSS`). O estado mutável fica em `current/` e `outputs/`, limpos a cada
run; o checkpointer SQLite (`thread_id = run_id`) permite `resume`. No `finalize`, `snapshot_run()` congela `current/`,
`outputs/` e o log em `runs/<run_id>/`, grava `metadata/<run_id>.json` e arquiva a spec em `archive/`. Um run pendente
(`current/run.json` com status diferente de `done`) bloqueia novas runs sem `--force`.

## Rodar

```bash
uv sync
cp .env.example .env                      # OPENAI_API_KEY (LangSmith opcional)
P=~/Codes/deepagents_jobapplier
uv run python -m app.main describe --project $P --to-ux        # 1. brief para o designer (+ copia para o ux-deep-agents)
#   -> suba o .md no "choose file" do ux-deep-agents e aprove as telas; ele gera o prototipo front-end
uv run python -m app.main build --latest-ux-run --project $P   # 2. Angular em $P/frontend + 3. integracao
uv run python -m app.main build --ux-run "~/UX Project/ux-deep-agents/workspace/runs/run_20261030_201036" --project $P
uv run python -m app.main build spec.md --screens screens.json --stitch stitch-html/ --dest /outro/destino
uv run python -m app.main integrate --project $P               # so a integracao, sobre um front-end ja entregue
uv run python -m app.main ask "Quais telas a ultima run gerou?" --project $P   # Q&A so leitura sobre runs e projeto
uv run python -m app.main list | resume [RUN_ID]               # --force inicia nova run mesmo com uma pendente
```

Um único gerador de Angular (D1): no `ux-deep-agents`, `FRONTEND_CODER=0` pula o `frontend_coder` e a checagem `ngc`;
o Angular vem só daqui, fiel às telas que o designer aprovou no Stitch.

Depois: `cd $P/frontend && npm install && npm start` (http://localhost:4200) com `uv run job-applier-web` no backend
(porta 8501, CORS liberado para 4200). Para servir o build pelo FastAPI: `ng build --base-href /app/` e abra http://localhost:8501/app/.

Variáveis: `OPENAI_API_KEY`, `MODEL`, `MODEL_ARCHITECT`, `MODEL_ANGULAR_CODER`, `MODEL_MAX_RETRIES`, `MAX_FIX_ROUNDS`,
`FRONTEND_CHECK`, `FRONTEND_DEST`, `UX_RUNS_DIR`, `UX_INPUTS_DIR`, `PROJECT_TEST_CMD`, `PROJECT_FORMAT_CMD`, `BUILDER_WORKSPACE`, `ANGULAR_CACHE`, bloco LangSmith.

## Docker

A imagem traz Python 3.12, `uv`, Node 22 e o cache Angular (template + `node_modules`) pré-instalado em `/opt/angular_cache`,
então `ngc` e `ng build` funcionam sem rede em cada run. O workspace, o projeto alvo e o workspace do `ux-deep-agents` entram
como volumes (`compose.yaml`): `./workspace` em `/app/workspace`, o projeto em `/target` e o workspace do UX em `/ux`
(`TARGET_PROJECT` e `UX_WORKSPACE` sobrescrevem os caminhos).

```bash
docker compose build
docker compose up -d                        # API em http://localhost:8010 (Swagger em /docs); BUILDER_PORT muda a porta
docker compose run --rm builder describe --project /target --to-ux
docker compose run --rm builder build --latest-ux-run --project /target
docker compose run --rm builder integrate --project /target
docker compose run --rm builder list
```

A API (`serve`, `app/api.py`) roda os mesmos comandos em background, uma run por vez. No host ela sai na 8010 porque a
interface web do `ux-deep-agents` usa a 8000; dentro do container a porta é 8000:

```bash
curl -X POST localhost:8010/runs -H 'content-type: application/json' \
  -d '{"mode": "build", "project": "/target"}'          # ux_run opcional; sem ele, a run mais recente do UX
curl localhost:8010/runs                                # lista com status e uso
curl localhost:8010/runs/<run_id>                       # metadata, notas de progresso, erro
curl localhost:8010/runs/<run_id>/events                # log jsonl da run
curl -X POST localhost:8010/ask -H 'content-type: application/json' \
  -d '{"question": "A ultima run compilou? Quanto custou?", "project": "/target"}'   # {"response": "..."}
```

`POST /ask` (e `python -m app.main ask "pergunta" [--project DIR]`) responde de forma síncrona com o deep agent em modo só
leitura sobre `metadata/`, `logs/`, `current/`, `outputs/`, `runs/`, `skills/` e, se informado, o projeto em `/project/`;
erros do agente voltam como 500 com o detalhe.

Sem compose: `docker build -t frontend-builder .`, `docker run --rm -p 8010:8000 --env-file .env -v ... frontend-builder` (API) ou `docker run --rm --env-file .env -v ./workspace:/app/workspace -v <projeto>:/target -v "<ux>/workspace":/ux frontend-builder build --latest-ux-run --project /target`.

Na integração, os testes do projeto alvo rodam dentro do container com `UV_PROJECT_ENVIRONMENT=/tmp/target-venv`
(`PROJECT_TEST_CMD` na imagem), para não tocar no `.venv` do host montado em `/target`. `ANGULAR_CACHE` aponta o cache
Angular para fora do volume do workspace.

### Versionar e publicar a imagem

A CI (`.github/workflows/ci.yml`) roda ruff, mypy, pytest e o build da imagem em cada PR; em cada push na `main` publica
`ghcr.io/guicondor1512-genai-bci/frontend-builder` com três tags: a `version` do `pyproject.toml`, `latest` e `sha-<commit>`,
e então chama o webhook `DEPLOY_HOOK` (secret do repositório) com a tag publicada, para o ambiente puxar a nova imagem;
sem o secret, a etapa de deploy é pulada.
Para lançar uma versão, suba `version` no `pyproject.toml` no PR. Para usar a imagem publicada, troque `build: .` por
`image: ghcr.io/guicondor1512-genai-bci/frontend-builder:latest` no `compose.yaml` (ou `docker pull`).

Publicação manual (exige o escopo `write:packages` no token do `gh`):

```bash
gh auth refresh -s write:packages
gh auth token | docker login ghcr.io -u guicondor1512-genAI-BCI --password-stdin
IMAGE=ghcr.io/guicondor1512-genai-bci/frontend-builder
VERSION=$(grep -m1 '^version' pyproject.toml | cut -d '"' -f2)
docker build -t frontend-builder .
docker tag frontend-builder "$IMAGE:$VERSION" && docker tag frontend-builder "$IMAGE:latest"
docker push "$IMAGE:$VERSION" && docker push "$IMAGE:latest"
```

## Testes e lint

```bash
uv run pytest -q                              # grafo com agente falso, sem LLM nem npm
TEST_FRONTEND_CHECK=1 uv run pytest -q        # idem, com ngc e ng build reais
uv run ruff check . && uv run ruff format --check .
uv run --with mypy mypy app                    # tipos (CI)
```
