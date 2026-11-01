"""Ciclo completo do grafo com um agente falso que escreve um app Angular minimo."""

import json
from pathlib import Path

from app import workspace as ws
from app.graph import GraphContext, build_graph

SPEC = "# Spec\n\n### `home` — Home (Atual)\nTela inicial.\n"


class FakeAgent:
    """Escreve o nucleo no PLANO e a tela no BUILD, como os subagents fariam."""

    def __init__(self):
        self.phases: list[str] = []

    def invoke(self, payload, config):
        text = payload["messages"][0]["content"]
        phase = text.split(":")[0]
        self.phases.append(phase)
        app = ws.ROOT / ws.FRONTEND / "src" / "app"
        if phase == "PLANO":
            (ws.ROOT / "current" / "architecture.md").write_text("| home | /home | screens/home/home.ts | HomeScreen |")
            (app / "core" / "api").mkdir(parents=True)
            (app / "core" / "api" / "providers.ts").write_text(
                "import { Provider } from '@angular/core';\nexport const API_PROVIDERS: Provider[] = [];\n"
            )
            (app / "app.routes.ts").write_text(
                "import { Routes } from '@angular/router';\nexport const routes: Routes = ["
                "{ path: '', pathMatch: 'full', redirectTo: 'home' },"
                "{ path: 'home', loadComponent: () => import('./screens/home/home').then(m => m.HomeScreen) }];\n"
            )
            (app / "app.ts").write_text(
                "import { Component } from '@angular/core';\nimport { RouterOutlet } from '@angular/router';\n"
                "@Component({ selector: 'app-root', imports: [RouterOutlet], template: `<router-outlet />` })\n"
                "export class App {}\n"
            )
        elif phase == "BUILD":
            (app / "screens" / "home").mkdir(parents=True)
            (app / "screens" / "home" / "home.ts").write_text(
                "import { Component, signal } from '@angular/core';\n"
                "@Component({ selector: 'app-home', template: `<h1>{{ title() }}</h1>` })\n"
                "export class HomeScreen { readonly title = signal('Home'); }\n"
            )
            (ws.ROOT / ws.FRONTEND / "README.md").write_text("# Front-end\n")
        return {"messages": [FakeMessage(f"{phase} ok")]}


class FakeMessage:
    def __init__(self, text):
        self.text = text
        self.tool_calls = []


def test_full_run(tmp_path: Path):
    spec = tmp_path / "screens.md"
    spec.write_text(SPEC)
    dest = tmp_path / "dest"
    agent = FakeAgent()
    graph = build_graph()
    result = graph.invoke(
        {"input_path": str(spec), "run_id": "run_test", "dest_dir": str(dest), "auto_approve": True},
        config={"configurable": {"thread_id": "run_test"}},
        context=GraphContext(agent=agent),
    )
    assert agent.phases == ["PLANO", "BUILD"]
    assert result["frontend_errors"] == [] and result["build_errors"] == []
    assert (dest / "src" / "app" / "screens" / "home" / "home.ts").exists()
    assert (dest / "package.json").exists() and (dest / "src" / "app" / "app.config.ts").exists()
    assert "## Verificacao" in (dest / "README.md").read_text()
    assert (ws.ROOT / "runs" / "run_test" / "outputs" / "frontend" / "src" / "app" / "app.ts").exists()
    assert (ws.ROOT / "archive" / "run_test__screens.md").exists()
    meta = json.loads((ws.ROOT / "metadata" / "run_test.json").read_text())
    assert meta["status"] == "done" and "src/app/screens/home/home.ts" in meta["files"]
    assert "project" in meta  # resume le o projeto daqui para montar /project/
    events = [e["event"] for e in ws.read_events("run_test")]
    assert events[:3] == ["ingest", "plan_phase_start", "plan_phase_end"]
    assert events[-1] == "finalize"


STITCH_HTML = (
    '<html><head><link href="https://fonts.googleapis.com/css2?family=Inter" rel="stylesheet"/>'
    '<script src="https://cdn.tailwindcss.com?plugins=forms"></script>'
    '<script id="tailwind-config">tailwind.config = '
    '{darkMode: "class", theme: {extend: {"colors": {"primary": "#123456"}}}}</script>'
    "</head><body><main>Tela</main></body></html>"
)


def test_ingest_copies_stitch_html_and_theme(tmp_path: Path):
    from app.graph import ingest

    spec = tmp_path / "screens.md"
    spec.write_text(SPEC)
    stitch = tmp_path / "stitch"
    stitch.mkdir()
    (stitch / "home.html").write_text(STITCH_HTML)
    (stitch / "home.png").write_bytes(b"png")
    ingest({"input_path": str(spec), "run_id": "run_s", "stitch_dir": str(stitch)})
    assert (ws.ROOT / "current" / "stitch" / "home.html").exists()
    assert not (ws.ROOT / "current" / "stitch" / "home.png").exists()
    index = (ws.ROOT / ws.FRONTEND / "src" / "index.html").read_text()
    styles = (ws.ROOT / ws.FRONTEND / "src" / "styles.css").read_text()
    assert "family=Inter" in index and "cdn.tailwindcss.com" not in index
    assert '@import "tailwindcss";' in styles and "--color-primary: #123456;" in styles
    event = ws.read_events("run_s")[0]
    assert event["stitch_theme"] is True and event["screen_sections"] == ["home"]
    assert (ws.ROOT / "current" / "screens" / "home.md").read_text().startswith("### `home`")
    assert (ws.ROOT / "current" / "screens" / "_common.md").exists()
