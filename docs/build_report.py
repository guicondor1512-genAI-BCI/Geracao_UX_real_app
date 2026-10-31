"""Gera docs/relatorio_frontend_builder.pdf: descricao do projeto, visao de negocio, debitos tecnicos e proximos passos.

Uso: uv run --with reportlab python docs/build_report.py [saida.pdf]
"""

import sys
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    CondPageBreak,
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "relatorio_frontend_builder.pdf"
FIG_RUNS = Path(__file__).parent / "versionamento_runs.jpeg"
INK = colors.HexColor("#1F2937")
ACCENT = colors.HexColor("#1D4ED8")
GRID = colors.HexColor("#CBD5E1")
HEAD = colors.HexColor("#E2E8F0")

ss = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=ss["Heading1"], textColor=ACCENT, spaceBefore=14, spaceAfter=8, fontSize=16)
H2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=INK, spaceBefore=10, spaceAfter=4, fontSize=12)
BODY = ParagraphStyle("body", parent=ss["BodyText"], fontSize=9.5, leading=13, textColor=INK, spaceAfter=5)
BUL = ParagraphStyle("bul", parent=BODY, leftIndent=12, bulletIndent=2, spaceAfter=2)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=8.5, leading=11, spaceAfter=0)
TITLE = ParagraphStyle("title", parent=ss["Title"], fontSize=22, textColor=ACCENT, spaceAfter=4)
SUB = ParagraphStyle("sub", parent=BODY, fontSize=10.5, textColor=colors.HexColor("#475569"))


def p(text, style=BODY):
    if style in (H1, H2):  # titulo nunca fica sozinho no fim da pagina; a tabela seguinte pode dividir
        return KeepTogether([CondPageBreak(5 * cm), Paragraph(text, style)])
    return Paragraph(text, style)


def bullets(items):
    return [Paragraph(f"• {i}", BUL) for i in items]


def table(rows, widths):
    data = [[p(c, CELL) for c in r] for r in rows]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEAD),
                ("GRID", (0, 0), (-1, -1), 0.4, GRID),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def flow():
    """Diagrama do fluxo de ponta a ponta, em caixas."""
    from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String

    steps = [
        ("Backend\n(codigo)", "/project/"),
        ("describe", "brief .md\n10 secoes"),
        ("ux-deep-agents", "telas, Stitch,\nprototipo"),
        ("build", "Angular 22\n<projeto>/frontend"),
        ("integrate", "CORS, /app,\ncontrato, checks"),
    ]
    w, h, gap, y = 88, 54, 18, 10
    d = Drawing(5 * w + 4 * gap, h + 20)
    for i, (title, sub) in enumerate(steps):
        x = i * (w + gap)
        d.add(Rect(x, y, w, h, fillColor=colors.HexColor("#EFF6FF"), strokeColor=ACCENT, strokeWidth=1))
        d.add(
            String(
                x + w / 2,
                y + h - 16,
                title.split("\n")[0],
                textAnchor="middle",
                fontSize=9,
                fillColor=ACCENT,
                fontName="Helvetica-Bold",
            )
        )
        for j, line in enumerate(sub.split("\n")):
            d.add(String(x + w / 2, y + h - 30 - j * 10, line, textAnchor="middle", fontSize=7.5, fillColor=INK))
        if i < len(steps) - 1:
            ax = x + w
            d.add(Line(ax, y + h / 2, ax + gap - 5, y + h / 2, strokeColor=INK))
            d.add(
                Polygon(
                    [ax + gap - 5, y + h / 2 - 3, ax + gap, y + h / 2, ax + gap - 5, y + h / 2 + 3],
                    fillColor=INK,
                    strokeColor=INK,
                )
            )
    return d


def figure(path, width):
    """Imagem com largura fixa e proporcao preservada."""
    img = Image(str(path))
    img.drawHeight = width * img.imageHeight / img.imageWidth
    img.drawWidth = width
    return img


def story():
    s = [
        p("frontend-builder", TITLE),
        p(
            "Deep Agent que transforma um backend existente em uma aplicacao Angular integrada, passando por um designer",
            SUB,
        ),
        p(f"Relatorio tecnico e de negocio - {date.today():%d/%m/%Y}", SUB),
        Spacer(1, 10),
        p("1. Resumo executivo", H1),
        p(
            "O frontend-builder e um agente (LangChain deepagents orquestrado por LangGraph) que fecha o ciclo entre um "
            "backend ja escrito e uma interface pronta para uso. Ele le o codigo do backend e escreve um brief para o designer; "
            "o brief alimenta o microservico ux-deep-agents, onde o designer aprova as telas; o prototipo aprovado vira uma "
            "aplicacao Angular 22 real, gravada dentro do projeto do backend e adaptada para funcionar com ele. "
            "Na primeira execucao completa sobre o Job Applier, o ciclo inteiro custou cerca de US$ 1 em tokens "
            "(gpt-6-luna) e 16 minutos de processamento, com o Angular compilando na primeira tentativa e os 146 testes do backend verdes. "
            "Desde 31/10/2026 as telas aprovadas no Stitch sao a fonte visual do Angular: tema, layout e icones chegam ao app real."
        ),
        p("2. O que o projeto faz", H1),
        flow(),
        Spacer(1, 6),
        p(
            "Tres comandos, todos sobre um projeto alvo (<i>--project DIR</i>), que os agentes enxergam como <i>/project/</i>:"
        ),
        *bullets(
            [
                "<b>describe</b>: o subagent <i>backend_analyst</i> le README, configuracao, rotas, modelos, estados e prompts do backend e "
                "escreve <i>outputs/brief/&lt;projeto&gt;-descricao.md</i> com 10 secoes fixas (o que e, personas, fluxos, entidades e estados, "
                "privacidade, telas atuais, direcoes futuras, tom, contrato da API). Com <i>--to-ux</i>, copia para os inputs do ux-deep-agents.",
                "<b>build</b>: a partir de uma run do ux-deep-agents (screens.md, screens.json e os HTML das telas aprovadas no Stitch, que sao a "
                "fonte visual: o tema Tailwind do Stitch vai para o index.html e cada tela e convertida a partir do seu HTML), o <i>architect</i> define "
                "arquitetura, design tokens, modelos, servicos de API (HTTP e mock) e componentes compartilhados; varios <i>angular_coder</i> implementam "
                "lotes de telas em paralelo; o pipeline compila com <i>ngc --noEmit</i> (strictTemplates) e <i>ng build</i>, com ate 5 rodadas de correcao.",
                "<b>integrate</b>: o <i>integrator</i> adiciona CORS e o mount de <i>/app</i> no FastAPI, desliga os mocks, confere o contrato do front-end "
                "contra as rotas reais, documenta e roda <i>black</i>, <i>pytest</i> e o build do Angular ate os tres passarem.",
            ]
        ),
        p("3. Arquitetura", H1),
        p("3.1 Agentes", H2),
        table(
            [
                ["Agente", "Papel", "Le", "Escreve"],
                [
                    "orquestrador",
                    "Recebe uma fase por vez do LangGraph; delega com task(); nunca implementa",
                    "spec, architecture.md",
                    "plan.md, README do front",
                ],
                ["backend_analyst", "Analista de produto que le codigo", "/project/**", "outputs/brief/*.md"],
                [
                    "architect",
                    "Arquitetura Angular, nucleo do app e contrato da API",
                    "spec, screens.json, referencia",
                    "architecture.md, app.ts, routes, core/**, shared/**",
                ],
                [
                    "angular_coder (N)",
                    "Um lote de 3-4 telas por instancia, em paralelo; converte o HTML do Stitch em componente; corrige erros do ngc",
                    "architecture.md, spec, stitch/&lt;id&gt;.html, core, shared",
                    "screens/&lt;id&gt;/&lt;id&gt;.ts",
                ],
                [
                    "integrator",
                    "Integracao back + front com a tool project_check",
                    "/project/**, frontend/**",
                    "main.py, config.py, environment.ts, READMEs",
                ],
            ],
            [3 * cm, 6 * cm, 4 * cm, 4.2 * cm],
        ),
        p("3.2 Pipelines LangGraph", H2),
        p(
            "<i>build</i>: ingest -> plan_phase -> build_phase -> verify_frontend -> (fix_phase ate MAX_FIX_ROUNDS) -> deliver -> "
            "integrate_phase -> verify_integration -> (integrate_fix, 1 rodada) -> finalize. <i>describe</i> e <i>integrate</i> sao grafos "
            "menores que reutilizam os mesmos nos. Cada fase grava um evento <i>&lt;fase&gt;_end</i> com duracao, tokens por modelo e "
            "quantas mensagens dispararam subagents em paralelo. Falhas viram evento <i>failed</i> e status em <i>current/run.json</i>; "
            "o checkpointer SQLite permite <i>resume</i>."
        ),
        Spacer(1, 6),
        KeepTogether(
            [
                figure(FIG_RUNS, 14.5 * cm),
                p(
                    "<b>Figura 1.</b> Versionamento de runs: cada execucao recebe um run_id; current/ e outputs/ sao o estado "
                    "mutavel, limpos a cada run; o checkpointer SQLite permite resume; no finalize o snapshot vai para "
                    "runs/&lt;run_id&gt;/ junto com metadata, log e a spec arquivada.",
                    CELL,
                ),
            ]
        ),
        p("3.3 Workspace e isolamento de contexto", H2),
        table(
            [
                ["Pasta", "Uso"],
                ["inputs/", "specs e briefs a processar"],
                ["current/", "run atual: spec.md, screens.json, stitch/ (HTML aprovado por tela), reference/, plan.md, architecture.md, run.json"],
                ["outputs/", "frontend/ gerado ou brief/ (limpo a cada run)"],
                ["logs/", "&lt;run_id&gt;.jsonl com eventos, tokens, erros do compilador e das checagens"],
                [
                    "metadata/",
                    "&lt;run_id&gt;.json: entradas, modo, status, arquivos gerados, uso, git status do projeto",
                ],
                ["skills/", "angular-app, jobapplier-api, ux-brief, integration (progressive disclosure via SKILL.md)"],
                ["runs/ e archive/", "snapshot imutavel de cada run e copia da spec processada"],
                [".angular_cache/", "template Angular + node_modules para ngc e ng build"],
            ],
            [3.5 * cm, 13.7 * cm],
        ),
        Spacer(1, 6),
        p(
            "Cada subagent recebe so a instrucao da sua task e le do disco o que precisa; o orquestrador nunca ve o conteudo das "
            "telas. A paralelizacao acontece quando o orquestrador dispara varias <i>task()</i> na mesma mensagem (o evento "
            "<i>parallel_task_calls</i> comprova)."
        ),
        p("3.4 Verificacao por compilador, nao por opiniao", H2),
        p(
            "Nenhum artefato e aceito pela palavra do modelo. O Angular passa por <i>ngc --noEmit</i> com strictTemplates e por "
            "<i>ng build</i> de producao; o backend por black e pela suite de testes; o brief pela checagem das 10 secoes. "
            "Os erros voltam ao subagent como texto do compilador, por arquivo."
        ),
        p("4. Resultados medidos (30/10/2026, projeto Job Applier)", H1),
        table(
            [
                ["Run", "Resultado", "Duracao", "Tokens", "Custo aprox."],
                [
                    "build (run UX run_20261030_201036)",
                    "11 telas, 30 arquivos; ngc e ng build ok na 1a tentativa",
                    "725 s",
                    "8,30 M",
                    "US$ 0,88",
                ],
                [
                    "integrate",
                    "CORS, /app, environment, contrato (achou o campo consent faltante em /voices); 146 testes ok",
                    "114 s",
                    "0,98 M",
                    "US$ 0,10",
                ],
                [
                    "describe",
                    "brief de 92 linhas, 10 secoes, copiado para o ux-deep-agents",
                    "103 s",
                    "0,95 M",
                    "US$ 0,10",
                ],
                [
                    "build + integrate com Stitch (31/10, run UX run_20261030_205257)",
                    "13 telas fieis ao tema do Stitch; 3 rodadas de ngc (12 -> 1 -> 6 -> 2 erros), ultimo erro corrigido na integracao; 146 testes e ng build ok",
                    "887 s",
                    "9,34 M",
                    "US$ 0,99",
                ],
            ],
            [4.2 * cm, 7 * cm, 1.7 * cm, 1.8 * cm, 2.3 * cm],
        ),
        p(
            "Para referencia, a run do ux-deep-agents que gerou o prototipo (telas, Stitch, prompts e prototipo Angular) custou "
            "2,26 M tokens e 17 minutos. O ciclo completo, do codigo do backend ao Angular integrado, fica em torno de "
            "12,5 M tokens, US$ 1,3 e 35 minutos de maquina, mais o tempo do designer na revisao."
        ),
        p("5. Visao estrategica de negocio", H1),
        p("5.1 Problema", H2),
        p(
            "Boa parte do software util nasce como backend, API ou CLI e nunca ganha uma interface decente: faltam designer, "
            "front-end e tempo. Quando ganha, o front-end e escrito a partir de conversas e capturas de tela, e o contrato "
            "da API se perde no caminho. Ferramentas de geracao de UI por IA (v0, Lovable, Bolt) partem de um prompt, nao de "
            "um sistema existente, e nao tem como garantir que o que geram conversa com o backend real."
        ),
        p("5.2 Proposta de valor", H2),
        *bullets(
            [
                "<b>Parte do codigo, nao do prompt.</b> O brief e extraido do backend: rotas, estados, limites e regras de privacidade reais. "
                "O designer recebe fatos, nao suposicoes.",
                "<b>Humano no circuito onde importa.</b> O designer aprova as telas (Stitch) antes de qualquer linha de Angular; o desenvolvedor "
                "recebe um diff revisavel no proprio repositorio.",
                "<b>Verificado por compilador e testes.</b> O resultado compila, faz build e nao quebra a suite do backend. Isso e o que separa "
                "um prototipo de um pull request.",
                "<b>Custo marginal perto de zero.</b> Cerca de US$ 1 por ciclo com gpt-6-luna; o custo dominante passa a ser o tempo do designer, "
                "nao o da engenharia.",
                "<b>Rastreavel.</b> Cada run tem snapshot, log de tokens por fase e metadata com o git status do projeto: da para auditar e comparar.",
            ]
        ),
        p("5.3 Para quem e como monetizar", H2),
        table(
            [
                ["Segmento", "Dor", "Oferta", "Modelo"],
                [
                    "Times de produto com backend forte e front fraco",
                    "Features ficam presas no Swagger",
                    "Ferramenta interna: brief + Angular + integracao a partir do repo",
                    "Licenca por repositorio ou por assento",
                ],
                [
                    "Agencias e consultorias de UX",
                    "Levantamento de requisitos e handoff manuais",
                    "describe como servico: brief + telas em horas",
                    "Por projeto; upsell do Angular",
                ],
                [
                    "Fornecedores de plataformas internas",
                    "Dezenas de servicos sem UI de operacao",
                    "Pipeline continuo: a cada mudanca de API, UI atualizada e verificada",
                    "SaaS por servico monitorado",
                ],
                [
                    "Equipes que migram front-end legado",
                    "Reescrita cara e arriscada",
                    "Brief do sistema atual + Angular novo com contrato preservado",
                    "Projeto fechado",
                ],
            ],
            [4 * cm, 4 * cm, 5.5 * cm, 3.7 * cm],
        ),
        p("5.4 Diferenciais defensaveis", H2),
        *bullets(
            [
                "O par <b>brief gerado do codigo + aprovacao do designer</b> e um ativo: cada run melhora skills e preferencias (a memoria do ux-deep-agents ja aprende do feedback).",
                "A <b>verificacao fechada</b> (compilador, build, testes, contrato) e dificil de copiar com prompt engineering puro e e o que permite entregar no repositorio do cliente.",
                "<b>Agnostico de modelo</b>: cada agente tem modelo configuravel; o pipeline inteiro rodou no modelo mais barato da familia GPT-6 sem perder qualidade mensuravel.",
            ]
        ),
        p("5.5 Riscos", H2),
        *bullets(
            [
                "Dependencia de um unico provedor de modelo e de um gerador de telas (Stitch) com limite de 60 s por tela.",
                "Qualidade visual: o Angular herda o prototipo em texto, nao o layout aprovado; sem design system real, o resultado e correto mas generico.",
                "Generalizacao: as convencoes de verificacao (uv, pytest, black) sao as do Job Applier; outros stacks exigem adaptacao.",
                "Concorrencia: v0/Lovable podem adicionar leitura de repositorio; a defesa esta na integracao verificada, nao na geracao.",
            ]
        ),
        p("6. Debitos tecnicos", H1),
        table(
            [
                ["#", "Debito", "Impacto", "Severidade"],
                [
                    "D1",
                    "RESOLVIDO em 31/10/2026: o builder consome os HTML das telas do Stitch (tema no index.html, layout por tela) e FRONTEND_CODER=0 desliga o frontend_coder do ux-deep-agents (um gerador so)",
                    "Validado: 13 telas com os tokens do tema; erros do ngc convergem em 3-4 rodadas",
                    "Fechado",
                ],
                [
                    "D2",
                    "Contrato da API copiado a mao na skill jobapplier-api; ja errou uma vez (consent em /voices), pego pelo integrator",
                    "Bugs de contrato silenciosos em cada mudanca do backend",
                    "Alta",
                ],
                [
                    "D3",
                    "Ciclo longo (~35 min) e revisao humana so nas telas do Stitch; o architecture.md nao e revisado antes do build",
                    "Correcoes tardias custam uma run inteira",
                    "Media",
                ],
                [
                    "D4",
                    "Hash routing e Tailwind via CDN (agora com o tema do Stitch) no app real; sem fallback de index.html em /app",
                    "Escolhas de prototipo em producao",
                    "Media",
                ],
                [
                    "D11",
                    "Correcoes do ngc em paralelo as vezes introduzem erros novos em outros arquivos (aspas em templates, ICU); so a rodada seguinte os pega",
                    "Mais rodadas; o limite subiu para 5",
                    "Baixa",
                ],
                [
                    "D5",
                    "Comandos de verificacao (pytest, black, uv) fixos por env; o describe nao detecta as convencoes do projeto",
                    "So funciona bem em projetos com o stack do Job Applier",
                    "Media",
                ],
                [
                    "D6",
                    "Nenhum teste ponta a ponta com o backend real (precisa de Postgres); a integracao e verificada por compilacao e testes unitarios",
                    "Erros de runtime (SSE, auth, multipart) so aparecem em uso",
                    "Media",
                ],
                [
                    "D7",
                    "Consumo de contexto alto: 1,1 M tokens na fase de plano e 7,2 M no build (spec e referencia relidas por cada subagent)",
                    "Custo cresce com o tamanho da spec; limite de contexto em apps maiores",
                    "Media",
                ],
                [
                    "D8",
                    "Frontmatter de skill invalido e ignorado silenciosamente pelo deepagents (aconteceu com integration); nao ha validacao no startup",
                    "Skill ausente sem erro visivel",
                    "Baixa",
                ],
                [
                    "D9",
                    "Apos falha, current/run.json fica como running e exige --force; resume existe mas nao foi exercitado em run real",
                    "Atrito operacional",
                    "Baixa",
                ],
                [
                    "D10",
                    "README do front-end gerado trouxe caminho virtual (/outputs/frontend) ate o integrator corrigir; textos as vezes sem acentos",
                    "Acabamento",
                    "Baixa",
                ],
            ],
            [0.9 * cm, 8.3 * cm, 5.3 * cm, 1.9 * cm],
        ),
        p("7. Proximos passos", H1),
        p(
            "Com D1 fechado, os passos 1 e 3 completam a virada de pipeline de demonstracao para ferramenta de equipe: contrato "
            "sempre correto e revisao humana barata antes do codigo, sobre um unico gerador fiel ao design aprovado."
        ),
        table(
            [
                ["Prioridade", "Passo", "Resolve", "Esforco"],
                [
                    "1",
                    "Gerar models.ts e o cliente HTTP a partir do /openapi.json do FastAPI (no describe e no integrate), eliminando a tabela manual da skill",
                    "D2",
                    "1-2 dias",
                ],
                [
                    "2",
                    "Feito (D1). Proximo nesta linha: comparar screenshot do Angular com o PNG do Stitch por tela (Playwright) e devolver diferencas ao angular_coder",
                    "D1 (qualidade visual)",
                    "2 dias",
                ],
                [
                    "3",
                    "Ponto de revisao humana no architecture.md (lista de telas, rotas, componentes) antes do build, via interrupt() como no ux-deep-agents",
                    "D3",
                    "1 dia",
                ],
                [
                    "4",
                    "Teste ponta a ponta: subir Postgres e backend em container, rodar o Angular com Playwright contra /ask, /review e SSE",
                    "D6",
                    "2 dias",
                ],
                [
                    "5",
                    "Detectar convencoes do projeto no describe (gerenciador, testes, formatador, porta) e gravar em metadata para o integrate",
                    "D5",
                    "1 dia",
                ],
                [
                    "6",
                    "Reduzir contexto: resumo por tela em vez da spec inteira para cada angular_coder; cache de prompt onde o provedor permitir",
                    "D7",
                    "1-2 dias",
                ],
                [
                    "7",
                    "Tailwind no build, fallback de index.html em /app, path routing; validar skills no startup; limpar run.json apos falha; lint de templates antes do ngc",
                    "D4, D8, D9, D11",
                    "1 dia",
                ],
                [
                    "8",
                    "Interface web do builder (mesmo padrao do ux-deep-agents): upload do projeto, acompanhamento das fases, diff para revisar e aprovar",
                    "Produto",
                    "3-5 dias",
                ],
                [
                    "9",
                    "Segundo projeto alvo com outro stack (ex.: Node/Express) para medir generalizacao e ajustar skills",
                    "D5, risco",
                    "2 dias",
                ],
            ],
            [1.8 * cm, 9.6 * cm, 2.6 * cm, 2.4 * cm],
        ),
    ]
    return s


def main():
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title="frontend-builder: relatorio tecnico e de negocio",
        author="Guilherme Tavares",
    )
    doc.build(story())
    print(f"PDF gerado em {OUT}")


if __name__ == "__main__":
    main()
