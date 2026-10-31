"""Conversao da config Tailwind v3 do Stitch para @theme do Tailwind v4."""

from app.theme import theme_css

CONFIG = """
    tailwind.config = {
      darkMode: "class",
      theme: {
        extend: {
          "colors": {"primary": "#000f22", "on-surface": "#1a1c1e"},
          "borderRadius": {"lg": "0.5rem"},
          "spacing": {"18": "4.5rem"},
          "fontFamily": {"headline-md": ["Inter"], "body": ["Inter", "Noto Sans"]},
          "fontSize": {"body-sm": ["12px", { "lineHeight": "16px", "fontWeight": "400" }], "plain": "15px"}
        }
      }
    }
"""


def test_theme_css():
    css = theme_css(CONFIG)
    assert css.startswith("@custom-variant dark (&:where(.dark, .dark *));\n@theme {")
    for line in (
        "  --color-primary: #000f22;",
        "  --color-on-surface: #1a1c1e;",
        "  --radius-lg: 0.5rem;",
        "  --spacing-18: 4.5rem;",
        "  --font-headline-md: Inter, sans-serif;",
        '  --font-body: Inter, "Noto Sans", sans-serif;',
        "  --text-body-sm: 12px;",
        "  --text-body-sm--line-height: 16px;",
        "  --text-body-sm--font-weight: 400;",
        "  --text-plain: 15px;",
    ):
        assert line in css, line
