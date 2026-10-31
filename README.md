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
build:     ingest -> plan_phase -> review_architecture --(aprovado | --auto-approve)--> build_phase -> verify_frontend --(erros)--> fix_phase
                              ^          '-- revise_architecture <-- (feedback, ate MAX_REVIEW_ROUNDS)          '--(ok)--> deliver
                                                                                        -> [integrate_phase -> verify_integration] -> finalize
integrate: ingest_integrate -> integrate_phase (integrator) -> verify_integration --(erros, 1 rodada)--> integrate_fix -> finalize
```

| Fase | Quem | O que faz |
|---|---|---|
| `ingest` | pipeline | copia spec, `screens.json`, `current/stitch/<id>.html`, injeta a config Tailwind do Stitch em `src/index.html` (`app/theme.py`) e, com `--project`, gera `current/openapi.json`, `current/contract.md` e `src/app/core/models.ts` do backend (`app/openapi.py`, `app/contract.py`) |
| `plan_phase` | orquestrador -> `architect` | `current/plan.md`, `current/architecture.md` (tela -> rota -> arquivo, design tokens e layout do Stitch, shared, modelos, serviços), núcleo do app (`app.ts`, `app.routes.ts`, `core/**`, `shared/**`) |
| `review_architecture` | revisor humano | pausa (`interrupt()`) com `architecture.md` e `plan.md`: aprovar segue; feedback grava `current/feedback.md` e volta ao `architect` (`revise_architecture`, até `MAX_REVIEW_ROUNDS`, default 3; depois segue com aviso). Terminal pergunta; API deixa a run `paused` até `POST /runs/{id}/decision`; `--auto-approve` pula |
| `build_phase` | orquestrador -> N x `angular_coder` em paralelo | um lote de telas por `task()`; cada tela converte o HTML do Stitch em `src/app/screens/<id>/<id>.ts` (estrutura e classes preservadas, conteúdo vira signals e `@for`, estados loading/vazio/erro); depois `README.md` |
| `verify_frontend` | pipeline | `ngc --noEmit` (strictTemplates) em `workspace/.angular_cache` |
| `fix_phase` | orquestrador -> `angular_coder` | corrige só os arquivos citados pelo `ngc` |
| `deliver` | pipeline | `ng build --configuration production` e cópia para `<projeto>/frontend` (ou `FRONTEND_DEST`) |
| `integrate_phase` | orquestrador -> `integrator` | CORS e `/app` no FastAPI, `useMocks: false`, contrato do front-end = backend, README; `project_check` até passar |
| `verify_integration` | pipeline | `contract` (rotas do cliente existem no openapi.json), `uvx black`, `pytest` do backend e `ngc` + `ng build` (`PROJECT_TEST_CMD`/`PROJECT_FORMAT_CMD` sobrescrevem) |
| `describe_phase` | orquestrador -> `backend_analyst` | `outputs/brief/<slug>-descricao.md` com as 10 seções da skill `ux-brief`; cópia em `inputs/` e, com `--to-ux`, em `UX_INPUTS_DIR` |
| `finalize` | pipeline | snapshot em `runs/<run_id>/`, `metadata/<run_id>.json` (inclui `git status` do projeto), spec arquivada |

O projeto alvo aparece para os agentes como `/project/` (`CompositeBackend`); o workspace continua em `/`.

O projeto Angular base (package.json, angular.json, tsconfig, main.ts, index.html com Tailwind via CDN,
`environments/environment.ts` com `apiBaseUrl`/`useMocks`, `app.config.ts` com HttpClient e Router) vem de
`app/templates/angular/`; os agentes geram só `src/app/**` e `README.md`. O app roda sem backend (`useMocks: true`)
com `MockJobApplierApi`; `HttpJobApplierApi` segue o contrato gerado do backend: a cada run com `--project`, o builder importa a
app FastAPI no venv do projeto, chama `app.openapi()` e grava `current/openapi.json`, `current/contract.md` (tabela de rotas,
corpos, respostas e schemas) e `src/app/core/models.ts` (uma interface por schema; nunca editado à mão). A checagem `contract`
da integração confere que toda rota usada em `src/app/core/api/*.ts` existe no schema (D2: sem contrato copiado à mão).

## Workspace

| Pasta | Uso |
|---|---|
| `workspace/inputs/` | specs `.md` a processar (ou use `--ux-run` / `--latest-ux-run`) |
| `workspace/current/` | run atual: `spec.md`, `screens.json`, `stitch/` (HTML aprovado por tela), `reference/` (protótipo anterior, opcional), `plan.md`, `architecture.md`, `run.json` |
| `workspace/outputs/frontend/` | projeto Angular gerado (limpo a cada run) |
| `workspace/logs/` | `<run_id>.jsonl`: eventos, duração e tokens por fase, erros do `ngc` |
| `workspace/metadata/` | `<run_id>.json`: entradas, status, arquivos gerados, uso, destino |
| `workspace/skills/` | `angular-app`, `api-contract`, `ux-brief`, `integration` (SKILL.md lidos pelos subagents) |
| `workspace/runs/` | snapshot imutável de cada run |
| `workspace/archive/` | cópia da spec processada |
| `workspace/.angular_cache/` | template + `node_modules` para `ngc`/`ng build` |

## Versionamento de runs

![Versionamento de runs](docs/versionamento_runs.jpeg)

O builder se alimenta de outros microserviços: o projeto backend alvo (`--project`, montado como `/project/`; por
exemplo `DeepJobFinderAgent` ou `deepagents_jobapplier`) e o snapshot de run do `ux-deep-agents` (`screens.md`,
`screens.json` e os HTML aprovados no Stitch). O `describe` fecha a ponta inicial do ciclo, gerando o brief que o designer
aprova no `ux-deep-agents`; o `deliver` + `integrate` fecham a final, escrevendo o Angular integrado de volta no projeto alvo.

Cada execução, disparada pela CLI, pela API HTTP (`POST /runs`) ou pelo Docker, recebe um `run_id` (`run_YYYYMMDD_HHMMSS`).
O estado mutável fica em `current/` e `outputs/`, limpos a cada run; o checkpointer SQLite (`thread_id = run_id`) permite
`resume`. No `finalize`, `snapshot_run()` congela `current/`, `outputs/` e o log em `runs/<run_id>/`, grava
`metadata/<run_id>.json` e arquiva a spec em `archive/`. Um run pendente (`current/run.json` com status diferente de `done`)
bloqueia novas runs sem `--force` (HTTP 409 na API).

## Como rodar

Três caminhos, todos com os mesmos comandos (`describe`, `build`, `integrate`, `ask`, `list`, `resume`):
o **terminal** (CLI, ideal para acompanhar as fases no console), a **web** (API HTTP, para disparar runs e consultar
status de outro sistema) e o **Docker** (imagem com tudo instalado, para rodar igual em qualquer máquina ou servidor).

### Pré-requisitos

```bash
uv sync                                   # Python 3.12 e dependências travadas (uv.lock)
cp .env.example .env                      # OPENAI_API_KEY obrigatória; OPENROUTER_API_KEY (fallback em 429) e LangSmith opcionais
node -v                                   # Node 22+ e npm, usados pelo ngc e ng build (não precisa no Docker)
P=~/Codes/deepagents_jobapplier           # projeto alvo (backend FastAPI); o Angular vai para $P/frontend
```

O fluxo completo é: `describe` gera o brief -> você sobe o `.md` no "choose file" do `ux-deep-agents` e aprova as telas no
Stitch -> `build` gera o Angular a partir dessa run e, com `--project`, já integra ao backend.

### 1. Terminal (CLI)

```bash
uv run python -m app.main describe --project $P --to-ux        # brief para o designer (+ cópia nos inputs do ux-deep-agents)
uv run python -m app.main build --latest-ux-run --project $P   # Angular em $P/frontend + integração com o backend
#   -> apos o architect, o terminal mostra current/architecture.md e pergunta: [s] aprovar | [n] devolver correcoes
uv run python -m app.main build --latest-ux-run --project $P --auto-approve   # sem a pausa (CI, scripts)
uv run python -m app.main build --ux-run "~/UX Project/ux-deep-agents/workspace/runs/run_20261030_205257" --project $P
uv run python -m app.main build spec.md --screens screens.json --stitch stitch-html/ --dest /outro/destino
uv run python -m app.main integrate --project $P               # só a integração, sobre um front-end já entregue
uv run python -m app.main ask "Quais telas a última run gerou?" --project $P   # pergunta ao agente (só leitura)
uv run python -m app.main list                                 # runs e status
uv run python -m app.main resume [RUN_ID]                      # retoma uma run interrompida ou pausada na revisao
```

O terminal mostra cada fase e cada subagent (`-> architect iniciou`, `<- angular_coder terminou (120s)`), as checagens
(`ngc`, `ng build`, `black`, `pytest`) e, no fim, duração, tokens, destino e o `git status` do projeto. Uma run por vez:
com uma run pendente em `workspace/current/run.json`, use `resume`, `list` ou `--force`.

**Revisão da arquitetura (D3).** O ponto barato de corrigir é antes do código: após o `architect` (~5 min), o build pausa e
mostra `current/architecture.md` (telas -> rotas -> arquivos, componentes de `/shared`, serviços, lotes). Aprovar segue para o
build; devolver correções grava `current/feedback.md`, o `architect` revisa (1 a 2 min) e a pergunta volta, até
`MAX_REVIEW_ROUNDS` (3); depois disso o build segue com aviso e as pendências vão aos `angular_coder`. Fechar o terminal no
meio deixa a run `paused`; `resume` reabre a pergunta.

### 2. Web (API HTTP)

```bash
uv run python -m app.main serve --port 8010   # Swagger em http://localhost:8010/docs (a 8000 costuma estar com o ux-deep-agents)
```

Os mesmos comandos viram requisições; as runs rodam em background, uma por vez (409 se houver pendente sem `force`):

```bash
curl -X POST localhost:8010/runs -H 'content-type: application/json' \
  -d '{"mode": "describe", "project": "'$P'", "to_ux": true}'
curl -X POST localhost:8010/runs -H 'content-type: application/json' \
  -d '{"mode": "build", "project": "'$P'"}'        # ux_run opcional; sem ele, a run mais recente do UX; auto_approve pula a revisao
curl localhost:8010/runs/<run_id>                  # status "paused": campo review traz round, architecture e plan
curl -X POST localhost:8010/runs/<run_id>/decision -H 'content-type: application/json' \
  -d '{"approved": false, "feedback": "junte as telas de busca num lote"}'   # ou {"approved": true}
curl localhost:8010/runs                           # lista com status e uso
curl localhost:8010/runs/<run_id>                  # metadata, notas de progresso, erro
curl localhost:8010/runs/<run_id>/events           # log jsonl da run
curl -X POST localhost:8010/ask -H 'content-type: application/json' \
  -d '{"question": "A última run compilou? Quanto custou?", "project": "'$P'"}'   # {"response": "..."}
```

`POST /ask` responde de forma síncrona com o deep agent em modo só leitura sobre `metadata/`, `logs/`, `current/`,
`outputs/`, `runs/`, `skills/` e o projeto; erros do agente voltam como 500 com o detalhe. `GET /health` para monitoração.

### 3. Docker

A imagem traz Python 3.12, `uv`, Node 22 e o cache Angular (template + `node_modules`) pré-instalado em `/opt/angular_cache`,
então `ngc` e `ng build` funcionam sem rede em cada run. O workspace, o projeto alvo e o workspace do `ux-deep-agents` entram
como volumes (`compose.yaml`): `./workspace` em `/app/workspace`, o projeto em `/target` e o workspace do UX em `/ux`
(`TARGET_PROJECT` e `UX_WORKSPACE` sobrescrevem os caminhos; `BUILDER_PORT` a porta do host, default 8010).

```bash
docker compose build                                   # ou docker pull ghcr.io/guicondor1512-genai-bci/frontend-builder:latest
docker compose up -d                                   # web: API em http://localhost:8010 (Swagger em /docs)
docker compose run --rm builder describe --project /target --to-ux      # terminal dentro do container
docker compose run --rm builder build --latest-ux-run --project /target
docker compose run --rm builder integrate --project /target
docker compose run --rm builder ask "Quais telas existem?" --project /target
docker compose run --rm builder list
docker compose logs -f builder                         # acompanhar a API
```

Sem compose: `docker build -t frontend-builder .` e `docker run --rm -p 8010:8000 --env-file .env -v ./workspace:/app/workspace -v $P:/target -v "$HOME/UX Project/ux-deep-agents/workspace":/ux frontend-builder` (API); qualquer subcomando
do CLI no fim do comando roda em vez da API.

Na integração, os testes do projeto alvo rodam dentro do container com `UV_PROJECT_ENVIRONMENT=/tmp/target-venv`
(`PROJECT_TEST_CMD` na imagem), para não tocar no `.venv` do host montado em `/target`. `ANGULAR_CACHE` aponta o cache
Angular para fora do volume do workspace.

### Depois de uma run

`cd $P/frontend && npm install && npm start` (http://localhost:4200) com `uv run job-applier-web` no backend (porta 8501,
CORS liberado para 4200). Para servir o build pelo FastAPI: `ng build --base-href /app/` e abra http://localhost:8501/app/.
Um único gerador de Angular (D1): no `ux-deep-agents`, `FRONTEND_CODER=0` pula o `frontend_coder`; o Angular vem só daqui,
fiel às telas aprovadas no Stitch.

### Variáveis

`OPENAI_API_KEY`, `MODEL`, `MODEL_ARCHITECT`, `MODEL_ANGULAR_CODER`, `MODEL_BACKEND_ANALYST`, `MODEL_INTEGRATOR`, `MODEL_ASK`,
`OPENROUTER_API_KEY` (fallback do mesmo modelo no OpenRouter em 429/5xx), `MODEL_MAX_RETRIES`, `MAX_FIX_ROUNDS`, `MAX_REVIEW_ROUNDS`, `FRONTEND_CHECK`, `FRONTEND_DEST`, `UX_RUNS_DIR`, `UX_INPUTS_DIR`, `PROJECT_TEST_CMD`,
`PROJECT_FORMAT_CMD`, `PROJECT_CMD_PREFIX` (prefixo dos comandos no projeto, ex.: `UV_PROJECT_ENVIRONMENT=...`), `OPENAPI_APP`
(app FastAPI a importar, default `job_applier.main:app`), `OPENAPI_URL` (buscar o schema de um servidor no ar), `BUILDER_WORKSPACE`,
`ANGULAR_CACHE`, bloco LangSmith.

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
