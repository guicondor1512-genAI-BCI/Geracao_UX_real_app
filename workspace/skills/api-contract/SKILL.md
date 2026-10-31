---
name: api-contract
description: Como o front-end consome o contrato da API gerado do openapi.json do backend (contract.md e models.ts), com SSE, multipart, auth e o fluxo do Job Applier.
---
# Contrato da API do backend (FastAPI, porta 8501)

Base URL: `environment.apiBaseUrl` (default http://localhost:8501). Swagger em /docs. Com `APP_PASSWORD` no backend,
toda chamada exige HTTP Basic (qualquer usuario + senha): o navegador pede uma vez; em fetch use `credentials: 'include'`.

## Fonte de verdade: contrato gerado
- /current/contract.md: tabela metodo | rota | parametros | corpo (json <Schema> ou multipart: campos) | resposta 200 e erros,
  mais os schemas com seus campos. Gerado de /current/openapi.json (o `app.openapi()` do FastAPI) a cada run.
- src/app/core/models.ts: uma interface por schema, gerada do mesmo openapi.json. NUNCA edite; tipos extras do front
  (ex.: `StreamMessage = Step | Reply`, requests auxiliares) vao em src/app/core/types.ts.
- Campos com `?` tem default no backend: nas respostas eles sempre vem (use `??` quando precisar de um valor).
- `text/event-stream` na resposta = SSE (ver abaixo); `multipart/form-data` = FormData com os campos listados;
  `string` com formato binary = arquivo. Nomes de campos em snake_case, como no backend.
- Se contract.md nao existir (projeto sem OpenAPI), derive o contrato lendo as rotas do backend em /project/.
- project_check('contract') confere que toda rota literal usada em src/app/core/api/*.ts existe no openapi.json.

## SSE (core/sse.ts)
`fetch(url, { method: 'POST', body, credentials: 'include' })`, leia `response.body.getReader()`, acumule texto, separe por
linha em branco, cada bloco tem linhas `data: <json>`; `JSON.parse` e distinga Step (`agent` e `text`) de Reply (`thread_id`).
Entregue como `Observable<Step | Reply>` ou callbacks. Trate `running: true` chamando /continue/stream ate `running: false`.

## Fluxo de busca no front-end
1. search-config: valida formulario + PDF + consent -> POST /ask/stream.
2. search-progress: mostra Steps (agent, text), contagens derivadas do texto quando possivel; ao receber Reply com running=true chama /continue/stream; com pending -> search-review; com response (sem pending) -> search-review em estado vazio mostrando response.
3. search-review: cards de `pending`; editor inline (GET /files/{job_id}/resume e cover_letter); manter/pular + motivo -> POST /review.
4. review-confirmed: `opened` + `learned`.
Treino: interview-select lista GET /applications?status=opened; POST /interviews; interview-ready linka /files/{job_id}/hr_interview[/pdf] e technical_interview; voz: POST /voices e GET /files/{job_id}/{kind}/audio.
Privacidade: GET /privacy; DELETE /runs/{run_id}. Custos: GET /runs/{run_id}/cost.

## Mocks (core/mock/data.ts + MockJobApplierApi)
Implementam a mesma classe abstrata com dados ficticios realistas (3 a 5 vagas, status variados, regras aprendidas, custos,
perguntas de entrevista) e `delay(300)`; `/ask` mock emite alguns Steps e depois um Reply com pending. Com `useMocks=false`
nada muda nas telas.
