"""Tema visual aprovado no Stitch: a config do Tailwind e as fontes do HTML gerado vao para o index.html do app."""

import re
from pathlib import Path

CDN = '<script src="https://cdn.tailwindcss.com"></script>'
CONFIG = re.compile(r'<script id="tailwind-config">.*?</script>', re.S)
TAILWIND_SRC = re.compile(r'<script src="https://cdn\.tailwindcss\.com[^"]*"></script>')
FONTS = re.compile(r'<link href="https://fonts\.googleapis\.com[^"]*" rel="stylesheet"/?>')


def stitch_theme(html: str) -> str | None:
    """Trecho de <head> com fontes, Tailwind (com plugins) e config do tema de uma tela do Stitch; None sem tema."""
    config = CONFIG.search(html)
    if not config:
        return None
    fonts = sorted(set(FONTS.findall(html)))
    tailwind = TAILWIND_SRC.search(html)
    return "\n  ".join([*fonts, tailwind.group(0) if tailwind else CDN, config.group(0)])


def apply_theme(stitch_dir: Path, index_html: Path) -> bool:
    """Substitui o Tailwind CDN do index.html pelo tema do primeiro HTML do Stitch; False se nao houver tema."""
    for page in sorted(stitch_dir.glob("*.html")):
        theme = stitch_theme(page.read_text(encoding="utf-8"))
        if theme:
            index_html.write_text(index_html.read_text(encoding="utf-8").replace(CDN, theme), encoding="utf-8")
            return True
    return False
