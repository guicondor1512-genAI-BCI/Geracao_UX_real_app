"""Spec fatiada por tela: cada angular_coder le so as secoes das suas telas (menos tokens por chamada, D7/D12)."""

import re
from pathlib import Path

HEADING = re.compile(r"^#{2,3} .*$", re.M)
BACKTICK_ID = re.compile(r"`([a-z0-9][a-z0-9-]*)`")


def sections(text: str, ids: list[str] | None = None) -> dict[str, str]:
    """{id: secao} por titulo `### ...` que cita um id de tela entre crases; `_common` tem o resto do documento.

    Um bloco vai do seu titulo (## ou ###) ate o proximo titulo; blocos ## e ### sem id de tela sao comuns a todas."""
    known = set(ids or [])
    heads = list(HEADING.finditer(text))
    out: dict[str, str] = {}
    common: list[str] = [text[: heads[0].start()] if heads else text]
    for i, head in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        block = text[head.start() : end]
        candidates = [c for c in BACKTICK_ID.findall(head.group(0)) if not known or c in known]
        if head.group(0).startswith("### ") and candidates:
            out[candidates[0]] = block.strip() + "\n"
        else:
            common.append(block)
    out["_common"] = "".join(common).strip() + "\n"
    return out


def write_sections(spec: Path, folder: Path, ids: list[str] | None = None) -> list[str]:
    """Grava folder/<id>.md por tela e folder/_common.md; devolve os ids encontrados."""
    parts = sections(spec.read_text(encoding="utf-8"), ids)
    folder.mkdir(parents=True, exist_ok=True)
    for name, body in parts.items():
        (folder / f"{name}.md").write_text(body, encoding="utf-8")
    return [k for k in parts if k != "_common"]
