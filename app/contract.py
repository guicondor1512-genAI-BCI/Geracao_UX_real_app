"""Contrato da API gerado do openapi.json: contract.md (para agentes e designer), models.ts (tipos do front-end) e a
checagem de que as rotas usadas pelo cliente HTTP existem no schema."""

import json
import re
from pathlib import Path

HEADER = "// Gerado de openapi.json pelo frontend-builder: nao edite; o arquivo e regravado a cada run.\n\n"
PATH_LITERAL = re.compile(r"[`'\"](/[^`'\"\s]+)[`'\"]")


def _ref(schema: dict) -> str:
    return schema["$ref"].rsplit("/", 1)[-1]


def ts_type(schema: dict) -> str:
    """Tipo TypeScript de um schema JSON (subconjunto que o pydantic/FastAPI emite)."""
    if "$ref" in schema:
        return _ref(schema)
    if "anyOf" in schema:
        return " | ".join(dict.fromkeys(ts_type(s) for s in schema["anyOf"]))
    if "enum" in schema:
        return " | ".join(json.dumps(v) if isinstance(v, str) else str(v) for v in schema["enum"])
    kind = schema.get("type")
    if kind == "null":
        return "null"
    if kind == "string":
        return "string"
    if kind in ("integer", "number"):
        return "number"
    if kind == "boolean":
        return "boolean"
    if kind == "array":
        item = ts_type(schema.get("items", {}))
        return f"({item})[]" if " | " in item else f"{item}[]"
    if kind == "object":
        if "properties" in schema:
            return "{ " + "; ".join(_fields(schema)) + " }"
        extra = schema.get("additionalProperties")
        return f"Record<string, {ts_type(extra) if isinstance(extra, dict) else 'unknown'}>"
    return "unknown"


def _fields(schema: dict) -> list[str]:
    required = set(schema.get("required", []))
    return [f"{n}{'' if n in required else '?'}: {ts_type(p)}" for n, p in schema.get("properties", {}).items()]


def typescript_models(spec: dict) -> str:
    """Uma interface (ou type) exportada por schema de components.schemas."""
    out = [HEADER.rstrip("\n"), ""]
    for name, schema in spec.get("components", {}).get("schemas", {}).items():
        if schema.get("description"):
            out.append("/** " + " ".join(schema["description"].split()) + " */")
        if schema.get("type") == "object" and "properties" in schema:
            out.append(f"export interface {name} {{")
            out.extend(f"  {f};" for f in _fields(schema))
            out.append("}")
        else:
            out.append(f"export type {name} = {ts_type(schema)};")
        out.append("")
    return "\n".join(out)


def _body(op: dict) -> str:
    content = op.get("requestBody", {}).get("content", {})
    for media, item in content.items():
        schema = item.get("schema", {})
        if media.startswith("multipart"):
            return "multipart: " + ", ".join(_fields(_resolve(schema))) if schema else "multipart"
        return f"json {ts_type(schema)}"
    return "-"


_SPEC: dict = {}


def _resolve(schema: dict) -> dict:
    return _SPEC["components"]["schemas"][_ref(schema)] if "$ref" in schema else schema


def _response(op: dict) -> str:
    content = op.get("responses", {}).get("200", {}).get("content", {})
    for media, item in content.items():
        if media == "application/json":
            return ts_type(item.get("schema", {}))
        return media
    return "-"


def _params(op: dict) -> str:
    parts = []
    for p in op.get("parameters", []):
        opt = "" if p.get("required") else "?"
        parts.append(f"{p['name']}{opt} ({p['in']}: {ts_type(p.get('schema', {}))})")
    return ", ".join(parts) or "-"


def contract_markdown(spec: dict) -> str:
    """Tabela metodo/rota/resumo/parametros/corpo/resposta e os schemas com seus campos."""
    global _SPEC
    _SPEC = spec
    info = spec.get("info", {})
    lines = [
        f"# Contrato da API: {info.get('title', '')} {info.get('version', '')} (gerado de openapi.json)",
        "",
        "| Metodo | Rota | Resumo | Parametros | Corpo | Resposta 200 |",
        "|---|---|---|---|---|---|",
    ]
    for path, ops in spec.get("paths", {}).items():
        for method, op in ops.items():
            summary = " ".join((op.get("summary") or op.get("description") or "").split())[:140]
            errors = ", ".join(c for c in op.get("responses", {}) if c not in ("200", "422"))
            resp = _response(op) + (f" (erros: {errors})" if errors else "")
            cells = [method.upper(), f"`{path}`", summary, _params(op), _body(op), resp]
            lines.append("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
    lines += ["", "## Schemas", ""]
    for name, schema in spec.get("components", {}).get("schemas", {}).items():
        if name in ("HTTPValidationError", "ValidationError"):
            continue
        fields = "; ".join(_fields(schema)) if "properties" in schema else ts_type(schema)
        lines.append(f"- **{name}**: {fields}")
    return "\n".join(lines) + "\n"


def used_paths(ts_source: str) -> list[str]:
    """Rotas literais usadas num cliente TypeScript, com `${x}` normalizado para `{}`."""
    found = []
    for m in PATH_LITERAL.finditer(ts_source):
        path = re.sub(r"\$\{[^}]*\}", "{}", m.group(1).split("?")[0])
        if path not in found:
            found.append(path)
    return found


def unknown_paths(ts_sources: list[str], spec: dict) -> list[str]:
    """Rotas usadas pelo cliente que nao sao (nem prefixo nem sufixo de) uma rota do schema."""
    known = [re.sub(r"\{[^}]*\}", "{}", p) for p in spec.get("paths", {})]
    used = [p for src in ts_sources for p in used_paths(src)]
    return [p for p in dict.fromkeys(used) if not any(k == p or k.startswith(p) or k.endswith(p) for k in known)]


def generate(project_dir: Path, current: Path, models_path: Path | None) -> dict:
    """Busca o schema do projeto e grava o contrato; devolve {"paths", "schemas"} ou {"error": ...} sem levantar."""
    from app import openapi

    try:
        return write_contract(openapi.fetch(project_dir), current, models_path)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"[:1000]}


def write_contract(spec: dict, current: Path, models_path: Path | None) -> dict:
    """Grava current/openapi.json, current/contract.md e (se dado) models.ts; devolve contagens para o log."""
    (current / "openapi.json").write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
    (current / "contract.md").write_text(contract_markdown(spec), encoding="utf-8")
    if models_path:
        models_path.parent.mkdir(parents=True, exist_ok=True)
        models_path.write_text(typescript_models(spec), encoding="utf-8")
    return {"paths": len(spec.get("paths", {})), "schemas": len(spec.get("components", {}).get("schemas", {}))}
