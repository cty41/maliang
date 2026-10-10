"""v1 document schemas; no project values or JSON Schema runtime dependency."""
from __future__ import annotations

import json
import math
import re
from importlib.resources import files
from pathlib import Path
from typing import Any


def schema_document(name: str) -> dict[str, Any]:
    if name not in {"art-family-contract", "sprite-slice-draft"}:
        raise ValueError("Unknown authoring schema")
    relative = f"schemas/v1/{name}.schema.json"
    installed = files("maliang_art").joinpath(relative)
    if installed.is_file():
        return json.loads(installed.read_text(encoding="utf-8"))
    return json.loads((Path(__file__).parents[3] / relative).read_text(encoding="utf-8"))


def schema_errors(value: Any, schema: dict, path: str, root: dict | None = None):
    """Validate the deliberately small keyword subset used by these documents."""
    root = schema if root is None else root
    if "$ref" in schema:
        node = root
        for part in schema["$ref"].removeprefix("#/").split("/"):
            node = node[part]
        yield from schema_errors(value, node, path, root)
        return
    kind = schema.get("type")
    valid = {"object": isinstance(value, dict), "array": isinstance(value, list),
             "string": isinstance(value, str), "boolean": isinstance(value, bool),
             "integer": isinstance(value, int) and not isinstance(value, bool),
             "number": isinstance(value, (int, float)) and not isinstance(value, bool)}
    if kind and not valid[kind]:
        yield path, "invalid", f"Provide {kind}; this value cannot be compiled."
        return
    if "const" in schema and (value != schema["const"] or type(value) is not type(schema["const"])):
        yield path, "unsupported", f"Only version {schema['const']} is supported."
    if "enum" in schema and value not in schema["enum"]:
        yield path, "unsupported", f"Choose one of {schema['enum']}."
    if kind == "object":
        for field in schema.get("required", []):
            if field not in value:
                yield f"{path}.{field}", "missing-decision", f"Decide {field}; no value is inferred."
        props = schema.get("properties", {})
        for field, child in value.items():
            if field not in props:
                yield f"{path}.{field}", "unsupported", "Unknown field; express this decision using the v1 document."
            else:
                yield from schema_errors(child, props[field], f"{path}.{field}", root)
    elif kind == "array":
        if len(value) < schema.get("minItems", 0):
            yield path, "missing-decision", f"Provide at least {schema['minItems']} explicit choices."
        if len(value) > schema.get("maxItems", len(value)):
            yield path, "unsupported", f"This slice supports at most {schema['maxItems']} choices."
        if schema.get("uniqueItems") and any(item in value[:i] for i, item in enumerate(value)):
            yield path, "invalid", "Choices must be distinct."
        for i, item in enumerate(value):
            yield from schema_errors(item, schema.get("items", {}), f"{path}[{i}]", root)
    elif kind == "string":
        if not value.strip() or len(value) < schema.get("minLength", 0):
            yield path, "missing-decision", "Provide a concrete decision, not blank text."
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            yield path, "invalid", "Value does not match the portable v1 format."
    elif kind in {"number", "integer"}:
        if isinstance(value, float) and not math.isfinite(value):
            yield path, "invalid", "Use a finite number."
        elif (value < schema.get("minimum", value) or value > schema.get("maximum", value)
              or ("exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"])):
            yield path, "invalid", "Number is outside the supported range."
