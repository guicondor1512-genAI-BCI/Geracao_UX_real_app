"""Tema visual aprovado no Stitch no app real: a config do Tailwind (v3, CDN) do HTML gerado vira um bloco @theme do
Tailwind v4 em src/styles.css (compilado no build) e os <link> de fontes vao para o index.html."""

import json
import re
from pathlib import Path

CONFIG = re.compile(r'<script id="tailwind-config">(.*?)</script>', re.S)
FONTS = re.compile(r'<link href="(https://fonts\.googleapis\.com[^"]*)" rel="stylesheet"/?>')
DARK = re.compile(r"darkMode:\s*['\"]class['\"]")
NAMESPACES = {"colors": "color", "borderRadius": "radius", "spacing": "spacing"}
FONT_SIZE_KEYS = {"lineHeight": "line-height", "letterSpacing": "letter-spacing", "fontWeight": "font-weight"}


def _extend(config_js: str) -> dict:
    """O objeto `extend: {...}` da config (JSON com chaves entre aspas), por casamento de chaves."""
    start = config_js.find("{", config_js.find("extend"))
    depth = 0
    for i in range(start, len(config_js)):
        depth += {"{": 1, "}": -1}.get(config_js[i], 0)
        if depth == 0:
            return json.loads(config_js[start : i + 1])
    raise ValueError("config do Tailwind sem fechamento de chaves")


def theme_css(config_js: str) -> str:
    """Bloco @theme (Tailwind v4) equivalente a config v3 do Stitch, com os mesmos nomes de classe."""
    extend = _extend(config_js)
    lines = []
    for section, prefix in NAMESPACES.items():
        for name, value in extend.get(section, {}).items():
            lines.append(f"  --{prefix}-{name}: {value};")
    for name, fonts in extend.get("fontFamily", {}).items():
        stack = ", ".join(f'"{f}"' if " " in f else f for f in fonts)
        lines.append(f"  --font-{name}: {stack}, sans-serif;")
    for name, spec in extend.get("fontSize", {}).items():
        size, extra = (spec[0], spec[1]) if isinstance(spec, list) else (spec, {})
        lines.append(f"  --text-{name}: {size};")
        for key, css in FONT_SIZE_KEYS.items():
            if key in extra:
                lines.append(f"  --text-{name}--{css}: {extra[key]};")
    dark = "@custom-variant dark (&:where(.dark, .dark *));\n" if DARK.search(config_js) else ""
    return dark + "@theme {\n" + "\n".join(lines) + "\n}\n"


def stitch_theme(html: str) -> tuple[str, list[str]] | None:
    """(bloco @theme, links de fontes) de uma tela do Stitch; None se o HTML nao tiver config do Tailwind."""
    config = CONFIG.search(html)
    if not config:
        return None
    return theme_css(config.group(1)), list(dict.fromkeys(FONTS.findall(html)))


def apply_theme(stitch_dir: Path, index_html: Path, styles_css: Path) -> bool:
    """Escreve o tema do primeiro HTML do Stitch em styles.css e as fontes no index.html; False se nao houver tema."""
    for page in sorted(stitch_dir.glob("*.html")):
        found = stitch_theme(page.read_text(encoding="utf-8"))
        if not found:
            continue
        css, fonts = found
        styles = styles_css.read_text(encoding="utf-8")
        styles_css.write_text(
            styles.rstrip() + "\n\n/* Tema aprovado no Stitch (" + page.name + ") */\n" + css, encoding="utf-8"
        )
        links = "".join(f'  <link href="{f}" rel="stylesheet">\n' for f in fonts)
        html = index_html.read_text(encoding="utf-8").replace("</head>", links + "</head>", 1)
        index_html.write_text(html, encoding="utf-8")
        return True
    return False
