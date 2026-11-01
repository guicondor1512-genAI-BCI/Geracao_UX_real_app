"""Fatiamento da spec por tela, nos dois formatos de titulo que o ux-deep-agents produziu."""

from app.spec import sections

PT = """# Spec
## Convencoes
- regra geral
## Telas
### `search-config` — Buscar vagas (Atual)
campos da busca
### `search-review` — Resultados
cards
## Fluxos
1. busca -> revisao
"""
EN = """# Spec
## Cross-screen rules
- rule
### 1. Candidate dashboard (`candidate-home`) — future direction
funnel
### 2. Job Search — setup (`search-setup`)
form
## Flow summary
a -> b
"""


def test_sections_pt():
    s = sections(PT, ["search-config", "search-review"])
    assert set(s) == {"search-config", "search-review", "_common"}
    assert s["search-config"].startswith("### `search-config`") and "campos da busca" in s["search-config"]
    assert "regra geral" in s["_common"] and "busca -> revisao" in s["_common"] and "cards" not in s["_common"]


def test_sections_en_without_ids():
    s = sections(EN)
    assert "funnel" in s["candidate-home"] and "form" in s["search-setup"]
    assert "rule" in s["_common"] and "a -> b" in s["_common"]
