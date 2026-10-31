---
name: jobapplier-api
description: Contrato da API FastAPI do backend Job Applier (deepagents_jobapplier) que o front-end Angular consome; use para models.ts, JobApplierApi e mocks.
---
# Job Applier backend API (FastAPI, porta 8501)

Base URL: `environment.apiBaseUrl` (default http://localhost:8501). Swagger em /docs. Com `APP_PASSWORD` no backend,
toda chamada exige HTTP Basic (qualquer usuario + senha): o navegador pede uma vez; em fetch use `credentials: 'include'`.

## Entidades (core/models.ts)
```ts
export type Status = 'drafted' | 'opened' | 'skipped' | 'closed' | 'expired' | 'interviewing';
export type PostedWithin = '24h' | '3d' | '1w';
export type DocumentKind = 'resume' | 'cover_letter' | 'hr_interview' | 'technical_interview';
export type Language = 'en' | 'pt' | 'es' | 'fr' | 'de' | 'it';
export interface Recommendation { score: number; summary: string; components: Record<string, number | null>; }
export interface Application {
  job_id: string; company: string; title: string; url: string; status: Status;
  files: Record<string, string>;            // kind -> caminho/URL do documento
  posted_at: string | null;                 // ISO date
  found_at: string | null;                  // ISO datetime
  recommendation: Recommendation | null;
  skip_reason: string;
}
export interface Step { agent: string; text: string; }   // evento de progresso (SSE)
export interface Reply {
  thread_id: string; running: boolean;
  pending: Application[] | null;            // vagas aguardando revisao
  response: string | null;                  // resposta final (ex.: sem resultados + requisitos nao atendidos)
  opened: Application[]; learned: string[]; // vagas abertas na revisao; regras aprendidas (ate 8)
}
export interface Privacy { consent_text: string; consent_version: string; retention_days: number; }
export interface RunCost { run_id: string; calls: number; input_tokens: number; output_tokens: number; cost_usd: number; by_step: Record<string, number>; by_job: Record<string, number>; }
export interface QuestionAudio { number: number; link: string; }
```

## Endpoints
| Metodo e rota | Corpo | Resposta |
|---|---|---|
| POST /ask | multipart/form-data: role, location, posted_within (24h/3d/1w), jobs_to_apply (1-10), resume (PDF), consent (true) | Reply (pending ou response; running=true => chamar /continue) |
| POST /ask/stream | mesmo multipart | SSE: eventos Step... e por fim um Reply |
| POST /continue | JSON {thread_id} | Reply |
| POST /continue/stream | JSON {thread_id} | SSE Step... + Reply |
| POST /review | JSON {thread_id, approved: string[], edits: {job_id: {resume?, cover_letter?}}, skip_reasons: {job_id: string}} | Reply (opened, learned) |
| POST /review/stream | mesmo JSON | SSE Step... + Reply |
| GET /applications?status=opened&status=interviewing | - | Application[] (mais recentes primeiro) |
| POST /interviews | JSON {job_id, hr_minutes (10-120, default 30), technical_minutes (10-120, default 30), consent: true} | Reply (response com relatorio) |
| POST /interviews/stream | mesmo JSON | SSE Step... + Reply |
| POST /voices | JSON {job_id, language (en/pt/es/fr/de/it), speed (0.5-2), pitch (0.5-2), consent: true} | Reply |
| POST /voices/stream | mesmo JSON | SSE Step... + Reply |
| GET /privacy | - | Privacy |
| DELETE /runs/{run_id} | - | {deleted_rows: number} |
| GET /runs/{run_id}/cost | - | RunCost |
| GET /files/{job_id}/{kind} | - | Markdown (text/plain) |
| GET /files/{job_id}/{kind}/pdf | - | PDF |
| GET /files/{job_id}/{kind}/audio | - | QuestionAudio[] (kind = hr_interview ou technical_interview) |
| GET /files/{job_id}/{kind}/audio/{number} | - | WAV |

Erros: 400 (consentimento ausente, PDF invalido), 401 (senha), 404 (documento), 409 (run ja terminou / vaga nao aberta).

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
