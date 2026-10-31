/** Configuracao do ambiente. apiBaseUrl aponta para o backend FastAPI do Job Applier (uv run job-applier-web). */
export const environment = {
  production: false,
  apiBaseUrl: 'http://localhost:8501',
  /** true: a aplicacao usa os servicos mock (core/mock) e roda sem backend. */
  useMocks: true,
};
