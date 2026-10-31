"""plan_tool: persiste o plano de execucao em current/plan.md (unica tool de planejamento do orquestrador)."""

from langchain_core.tools import tool

from app.workspace import ROOT


@tool
def plan_tool(plan_markdown: str) -> str:
    """Salva/atualiza o plano de trabalho (markdown com etapas, subagent responsavel, telas por lote e status)
    em current/plan.md. Chame no inicio e sempre que o plano mudar."""
    path = ROOT / "current" / "plan.md"
    path.write_text(plan_markdown, encoding="utf-8")
    return f"Plano salvo em {path.relative_to(ROOT)} ({len(plan_markdown)} chars)."
