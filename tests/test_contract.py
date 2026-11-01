"""Geracao de contract.md e models.ts a partir de um OpenAPI minimo, e checagem das rotas do cliente."""

import json
from pathlib import Path

from app import contract

SPEC = {
    "openapi": "3.1.0",
    "info": {"title": "Job Applier", "version": "0.1.0"},
    "paths": {
        "/ask": {
            "post": {
                "summary": "Start a run.",
                "requestBody": {
                    "content": {"multipart/form-data": {"schema": {"$ref": "#/components/schemas/Body_ask"}}}
                },
                "responses": {
                    "200": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/Reply"}}}}
                },
            }
        },
        "/ask/stream": {"post": {"responses": {"200": {"content": {"text/event-stream": {}}}}}},
        "/applications": {
            "get": {
                "parameters": [
                    {
                        "name": "status",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "anyOf": [{"type": "array", "items": {"enum": ["opened", "skipped"]}}, {"type": "null"}]
                        },
                    }
                ],
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {
                                "schema": {"type": "array", "items": {"$ref": "#/components/schemas/Application"}}
                            }
                        }
                    }
                },
            }
        },
        "/files/{job_id}/{kind}/pdf": {"get": {"responses": {"200": {"content": {"application/pdf": {}}}}}},
        "/runs/{run_id}": {"delete": {"responses": {"200": {}, "404": {}}}},
    },
    "components": {
        "schemas": {
            "Body_ask": {
                "type": "object",
                "properties": {"role": {"type": "string"}, "resume": {"type": "string", "format": "binary"}},
                "required": ["role", "resume"],
            },
            "Application": {
                "description": "One job tracked across runs.",
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "status": {"type": "string", "enum": ["opened", "skipped"], "default": "opened"},
                    "files": {"type": "object", "additionalProperties": {"type": "string"}},
                    "posted_at": {"anyOf": [{"type": "string", "format": "date"}, {"type": "null"}]},
                    "score": {"type": "number"},
                },
                "required": ["job_id"],
            },
            "Reply": {
                "type": "object",
                "properties": {"pending": {"type": "array", "items": {"$ref": "#/components/schemas/Application"}}},
            },
            "HTTPValidationError": {
                "type": "object",
                "properties": {"detail": {"type": "array", "items": {"type": "string"}}},
            },
        }
    },
}

CLIENT = """
this.http.post<Reply>(this.url('/ask'), body);
postSse(this.url('/ask/stream'), body);
this.http.get(`${this.baseUrl}/files/${encodeURIComponent(jobId)}/${kind}/pdf`);
this.http.delete(`/runs/${runId}`);
this.http.get('/applications?status=opened');
this.http.get('/companies');
"""


def test_typescript_models():
    ts = contract.typescript_models(SPEC)
    assert "export interface Application {" in ts
    assert "  job_id: string;" in ts and '  status?: "opened" | "skipped";' in ts
    assert "  files?: Record<string, string>;" in ts and "  posted_at?: string | null;" in ts
    assert "  pending?: Application[];" in ts and "/** One job tracked across runs. */" in ts
    assert ts.startswith("// Gerado de openapi.json")


def test_contract_markdown():
    md = contract.contract_markdown(SPEC)
    assert "| POST | `/ask` | Start a run. | - | multipart: role: string, resume: string | Reply |" in md
    assert 'status? (query: ("opened" \\| "skipped")[] \\| null)' in md
    assert "| POST | `/ask/stream` |" in md and "text/event-stream" in md
    assert "Application[]" in md
    assert "(erros: 404)" in md and "- **Application**: job_id: string; status?:" in md
    assert "HTTPValidationError" not in md


def test_unknown_paths():
    assert contract.used_paths(CLIENT)[:2] == ["/ask", "/ask/stream"]
    assert contract.unknown_paths([CLIENT], SPEC) == ["/companies"]


def test_unknown_paths_query_and_literal_segments():
    spec = {"paths": {"/applications": {}, "/files/{job_id}/{kind}/audio/{number}": {}}}
    client = "get(`/applications${query}`); link: `/files/${jobId}/${kind}/audio/1`; get('/nope/${x}')"
    assert contract.used_paths(client) == ["/applications", "/files/{}/{}/audio/1", "/nope/{}"]
    assert contract.unknown_paths([client], spec) == ["/nope/{}"]


def test_write_contract(tmp_path: Path):
    current = tmp_path / "current"
    current.mkdir()
    models = tmp_path / "fe" / "src" / "app" / "core" / "models.ts"
    counts = contract.write_contract(SPEC, current, models)
    assert counts == {"paths": 5, "schemas": 4}
    assert json.loads((current / "openapi.json").read_text())["info"]["title"] == "Job Applier"
    assert (current / "contract.md").exists() and models.read_text().startswith("// Gerado")
