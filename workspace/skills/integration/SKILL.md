---
name: integration
description: "Como fazer o front-end Angular entregue em <projeto>/frontend e o backend (FastAPI) do projeto funcionarem juntos - CORS, servir o build, environment, contrato da API, testes e formatacao."
---
# Integracao back-end + front-end

## Quando usar
Na fase INTEGRATE, com o backend em /project/ e o Angular em /project/frontend (ou no caminho informado).
O backend e a fonte de verdade do contrato: adapte o front-end a ele; mude o backend so para servir o front-end.

## Passos
1. Leia o backend: arquivo FastAPI com as rotas (ex.: /project/src/<pacote>/main.py), modelos pydantic das respostas,
   autenticacao (ex.: HTTP Basic com APP_PASSWORD), como os estaticos sao servidos hoje.
2. Leia o front-end: src/environments/environment.ts, src/app/core/models.ts, core/api/http-job-applier-api.ts,
   core/api/job-applier-api.ts, core/sse.ts.
3. Backend (edicoes minimas, no mesmo estilo do arquivo):
   - CORS: `from fastapi.middleware.cors import CORSMiddleware` e `app.add_middleware(CORSMiddleware, allow_origins=FRONTEND_ORIGINS,
     allow_credentials=True, allow_methods=["*"], allow_headers=["*"])`, com `FRONTEND_ORIGINS` lido do ambiente
     (default `["http://localhost:4200"]`) em config.py. Registre ANTES de outros middlewares HTTP.
   - Servir o build com fallback de SPA (o Angular usa path routing, sem `#`): se `frontend/dist/<nome>/browser/index.html` existir,
     registre `@app.get("/app/{path:path}", include_in_schema=False)` que devolve `FileResponse` do arquivo pedido quando ele existir
     dentro de `browser/` (assets, js, css) e, caso contrario, do `index.html` (rotas profundas e refresh funcionam); `/app` sem barra
     redireciona para `/app/`. Um `app.mount("/app", StaticFiles(html=True))` NAO basta: devolve 404 em `/app/search-setup`.
     O build e `npm run build:app` (`ng build --configuration production --base-href /app/`); registre isso no README.
   - Nao altere rotas, modelos nem regras de negocio existentes. Nao quebre a pagina atual em `/`.
4. Front-end:
   - environment.ts: `useMocks: false`, `apiBaseUrl` = origem do backend (http://localhost:8501). Mantenha os mocks para desenvolvimento.
   - Confira metodo a metodo de JobApplierApi contra as rotas reais: caminho, metodo HTTP, nomes de campos (snake_case do backend),
     tipos (datas como string ISO), multipart em /ask, corpos JSON nos demais, `credentials: 'include'`/`withCredentials: true` para Basic auth.
   - SSE: Step {agent,text} e Reply {thread_id, running, pending, response, opened, learned}; `running: true` -> /continue/stream.
   - Links de documentos: `${apiBaseUrl}/files/{job_id}/{kind}` e `/pdf`, audio em `/files/{job_id}/{kind}/audio[/{n}]`.
5. Documente: secao "Front-end Angular" no /project/README.md (como rodar em dev com CORS, como buildar e servir em /app, variaveis).
   No README do front-end, troque caminhos virtuais do workspace (ex.: `cd /outputs/frontend`) pelo caminho real (`cd frontend`).
6. Verifique com project_check: 'format' (black), 'tests' (pytest do backend), 'frontend_build' (ngc + ng build). Repita ate passar.
   Se um teste existente quebrar por causa da sua mudanca, corrija a mudanca, nao o teste.

## Regras
- Edicoes cirurgicas com edit_file; nunca reescreva main.py inteiro. Siga o estilo do projeto (black, docstrings curtas, sem comentarios supérfluos).
- Nao adicione dependencias novas ao backend (CORSMiddleware e StaticFiles ja vem com o FastAPI/Starlette).
- Nao toque em .env, bancos, uv.lock, node_modules ou arquivos de deploy, salvo o README.
