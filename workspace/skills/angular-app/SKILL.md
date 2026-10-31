---
name: angular-app
description: Como construir a aplicacao Angular 22 real do Job Applier (standalone, signals, rotas lazy, HttpClient + mocks) a partir da spec de telas e do prototipo.
---
# Angular App (Angular 22, aplicacao real)

## Quando usar
Ao gerar /outputs/frontend/ a partir de /current/spec.md, /current/screens.json e /current/architecture.md.
O projeto base ja existe e NAO deve ser reescrito: package.json, angular.json, tsconfig*.json, src/main.ts,
src/index.html (Tailwind via CDN), src/styles.css (tem .sr-only), src/environments/environment.ts
(`apiBaseUrl`, `useMocks`) e src/app/app.config.ts (provideHttpClient, provideRouter com
withComponentInputBinding e `...API_PROVIDERS` importado de ./core/api/providers).

## Fonte visual: HTML do Stitch (/current/stitch/<id>.html)
Cada tela aprovada pelo designer existe como HTML + Tailwind. Ele manda no visual: estrutura, classes, cores (nomes do tema
como `bg-surface-container`, `text-on-surface`, `bg-primary`), fonte Inter e icones Material Symbols (`<span class="material-symbols-outlined">`).
A config do tema ja esta em src/index.html; use os nomes das cores do tema, nao hexadecimais. Converta so o conteudo do
<body> para o template; troque texto fixo por signals, listas repetidas por `@for` com dados de JobApplierApi, e acrescente
os estados (loading/vazio/erro) que o HTML estatico nao mostra. Nunca copie <html>, <head> ou scripts.

## Layout de pastas (gere exatamente assim)
- src/app/app.ts                       -> `App` (selector app-root): shell com header, nav (routerLink + routerLinkActive) e <router-outlet />
- src/app/app.routes.ts                -> uma rota por tela com `loadComponent: () => import('./screens/<id>/<id>').then(m => m.<Pascal>Screen)`; '' redireciona para a primeira; '**' para uma tela not-found simples
- src/app/core/models.ts               -> tipos TypeScript espelhando o contrato do backend (skill jobapplier-api)
- src/app/core/api/job-applier-api.ts  -> `export abstract class JobApplierApi { ... }` com um metodo por endpoint (retorna Observable<T> ou Promise<T>)
- src/app/core/api/http-job-applier-api.ts -> `HttpJobApplierApi extends JobApplierApi` com HttpClient e environment.apiBaseUrl
- src/app/core/api/mock-job-applier-api.ts -> `MockJobApplierApi extends JobApplierApi` com dados de core/mock e `delay()` curto
- src/app/core/api/providers.ts        -> `export const API_PROVIDERS: Provider[] = [{ provide: JobApplierApi, useClass: environment.useMocks ? MockJobApplierApi : HttpJobApplierApi }]`
- src/app/core/mock/data.ts            -> dados ficticios tipados (reutilize o que fizer sentido de /current/reference)
- src/app/core/sse.ts                  -> leitura de text/event-stream com fetch + ReadableStream (EventSource nao faz POST)
- src/app/shared/<kebab>.ts            -> componentes usados em mais de uma tela (page-header, status-badge, empty-state, error-banner, loading, data-table...)
- src/app/screens/<id>/<id>.ts         -> um componente standalone por tela, template inline, classe `<Pascal>Screen`, selector `app-<id>`

## Regras Angular (compila com strictTemplates)
- Standalone por padrao: NAO escreva `standalone: true` nem NgModules. Importe no `imports` so o que o template usa.
- Estado com signals: `signal()`, `computed()`, `input()`, `output()`, `linkedSignal()`; sem decorators @Input/@Output; sem BehaviorSubject para estado local.
- Control flow nativo `@if / @for (x of xs(); track x.id) / @switch`; nunca *ngIf/*ngFor nem CommonModule. Pipes: importe `DatePipe`, `DecimalPipe`, `CurrencyPipe` individualmente de @angular/common.
- Injecao com `inject()`: `private readonly api = inject(JobApplierApi);` `private readonly router = inject(Router);`
- Chamadas HTTP: `this.api.x().subscribe({ next: v => this.data.set(v), error: e => this.error.set(mensagem(e)) })`. Sempre estados loading/empty/error em signals.
- Formularios: `ReactiveFormsModule` com `inject(NonNullableFormBuilder)`; validacao com mensagens de erro ligadas por `aria-describedby`; botao desabilitado enquanto invalido ou carregando.
- Upload: `<input type="file" accept="application/pdf" (change)="onFile($event)">` e `FormData` no servico.
- Tipos estritos: sem `any`; `noPropertyAccessFromIndexSignature` (use `obj['chave']` em index signatures); `noImplicitReturns`.
- Zoneless (sem zone.js): nunca dependa de deteccao automatica apos `setTimeout`; atualize signals.
- Nada alem de @angular/*, rxjs e Tailwind (classes utilitarias). Sem bibliotecas externas.

## Acessibilidade (WCAG 2.1 AA)
- Status sempre texto + icone, nunca so cor. Tokens: sucesso #1B7F3B, erro #B3261E, neutro #4B5563, aviso #92400E (>= 4.5:1 sobre branco).
- Foco visivel: `focus-visible:ring-2 focus-visible:ring-offset-2`; nunca `outline-none` sem substituto.
- Tabelas com `<caption class="sr-only">`, `scope="col"`, `aria-sort` quando ordenavel. Regioes dinamicas com `aria-live="polite"`.
- Audio nunca toca sozinho; controles nativos `<audio controls>` com texto alternativo.

## Isolamento entre tarefas paralelas
Cada task do angular_coder recebe a lista de telas e os caminhos que pode escrever. Escreva SOMENTE esses arquivos.
Se precisar de um componente compartilhado que nao existe, crie-o em src/app/shared/ com nome unico e informe no retorno.
Nunca edite app.routes.ts, app.ts, core/** ou arquivos de outras telas a menos que a tarefa peca.

## Correcao de erros do ngc
Quando a mensagem trouxer erros `src/app/...:linha:coluna - error TSxxxx`, corrija apenas os arquivos citados e explique em uma linha cada correcao.
