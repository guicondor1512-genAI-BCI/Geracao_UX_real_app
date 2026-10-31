---
name: ux-brief
description: Como ler o backend de um projeto (/project/) e escrever o .md que explica o fluxo do software para um designer prototipar as telas (entrada do ux-deep-agents).
---
# UX brief a partir do backend

## Quando usar
Ao escrever /outputs/brief/<slug>-descricao.md a partir do codigo em /project/. O leitor e um designer de produto que NAO
le codigo: ele vai transformar o texto em telas. O arquivo sera a entrada do pipeline ux-deep-agents.

## Como ler o projeto (ordem)
1. /project/README.md e /project/CLAUDE.md (se existir): proposito, comandos, arquitetura.
2. /project/pyproject.toml ou package.json: nome, scripts, dependencias (frameworks web, agentes, bancos).
3. API: arquivos com rotas (FastAPI `@app.get/post`, Flask, Express, controllers). Liste cada endpoint, corpo, resposta e erro.
4. Entidades e estados: modelos pydantic/ORM/TypedDict, enums e Literals de status, tabelas, transicoes.
5. Fluxos: prompts do agente/orquestrador, CLI, paginas estaticas (static/*.html), templates: o que o usuario faz passo a passo.
6. Privacidade, autenticacao, custos, observabilidade: o que precisa aparecer na interface.
Ignore .venv, node_modules, caches, bancos (*.db, *.sqlite), locks e arquivos binarios. Nao leia arquivos acima de 200 KB.

## Estrutura obrigatoria do .md (mesma ordem; titulos em portugues)
```
# <Nome do produto> - descricao do produto para prototipacao de telas
## 1. O que e                      (2-4 paragrafos: proposito, principio central, como e entregue hoje: CLI/web/API/Docker)
## 2. Para quem                    (personas, contexto de uso, sessao tipica, restricoes como usuario unico/senha)
## 3. Fluxo principal: <nome>      (passos numerados do que o usuario faz e do que o sistema faz por baixo; estados de espera; caso sem resultados)
## 4. Fluxo secundario: <nome>     (um bloco por fluxo adicional existente)
## 5. Entidades e estados (o que as telas precisam mostrar)   (cada entidade com campos relevantes e maquina de estados em texto)
## 6. Privacidade / seguranca (deve ser visivel na interface) (consentimento, mascaramento, retencao, exclusao, autenticacao)
## 7. Telas que existem hoje       (uma linha por tela/aba/pagina atual, com seus blocos; o que fica fora do app: Swagger, dashboards)
## 8. Direcoes para o app do futuro (sugestoes para o prototipo)   (lista de ideias derivadas do codigo: dados que existem mas nao aparecem, TODOs, eventos SSE sem UI; marcadas como sugestao)
## 9. Tom e identidade atuais      (logo, imagens, linguagem, contraste serio x leve)
## 10. Contrato da API (resumo para o handoff)   (tabela metodo+rota | corpo | resposta | erros; enums e faixas de valores)
```

## Regras
- So o que o codigo sustenta. Diferencie SEMPRE "existe hoje" de "sugestao" (secao 8 e marcadores "(futuro)").
- Cite nomes reais de status, campos, rotas e limites (ex.: 1-10 vagas, 30 min default, status `drafted -> opened -> interviewing`).
- Linguagem direta, frases curtas, sem jargao de codigo fora da secao 10; nada de trechos de codigo.
- Explique estados de espera e erro: o designer precisa desenhar carregando, vazio, erro, sucesso.
- Portugues do Brasil. Tamanho alvo: 90 a 160 linhas.
