from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml


@dataclass
class OperationDoc:
    doc_id: str
    method: str
    path: str
    tag: str
    summary: str
    description: str
    text: str


def _ref_name(ref: str) -> str:
    return ref.split("/")[-1]


def _resolve_ref(spec: dict, ref: str) -> dict | None:
    parts = ref.strip("#/").split("/")
    node: Any = spec
    for part in parts:
        node = node.get(part, {})
        if node is None:
            return None
    return node if isinstance(node, dict) else None


def _format_schema(
    spec: dict,
    schema: dict | str,
    indent: int = 0,
    required_fields: set[str] | None = None,
) -> str:
    if isinstance(schema, str):
        return " " * indent + schema

    ref = schema.get("$ref")
    if ref:
        resolved = _resolve_ref(spec, ref)
        if resolved:
            return _format_schema(spec, resolved, indent, required_fields)
        return " " * indent + _ref_name(ref)

    all_of = schema.get("allOf")
    any_of = schema.get("anyOf")
    one_of = schema.get("oneOf")

    if all_of:
        parts = []
        for sub in all_of:
            parts.append(_format_schema(spec, sub, indent, required_fields))
        return "\n".join(parts)

    if any_of or one_of:
        variants = any_of or one_of
        parts = []
        for sub in variants:
            parts.append(_format_schema(spec, sub, indent, required_fields))
        return "\n".join(parts)

    schema_type = schema.get("type", "object")
    desc = schema.get("description", "")
    enum_vals = schema.get("enum")

    if schema_type == "object":
        props = schema.get("properties", {})
        if not props:
            line = " " * indent + f"(object){(' — ' + desc) if desc else ''}"
            if enum_vals:
                line += f" Enum: {', '.join(str(v) for v in enum_vals)}"
            return line

        lines = []
        obj_required = set(schema.get("required", []))
        for name, prop in props.items():
            is_req = name in obj_required or (required_fields and name in required_fields)
            req_marker = "required" if is_req else "optional"
            prop_text = _format_property(spec, name, prop, req_marker, indent)
            lines.append(prop_text)
        return "\n".join(lines)

    if schema_type == "array":
        items = schema.get("items", {})
        item_text = _format_schema(spec, items, indent + 2)
        header = " " * indent + f"Array of:{(' — ' + desc) if desc else ''}"
        return header + "\n" + item_text

    line = " " * indent + f"Type: {schema_type}"
    if desc:
        line += f" — {desc}"
    if enum_vals:
        line += f". Enum: {', '.join(str(v) for v in enum_vals)}"
    example = schema.get("example")
    if example is not None:
        line += f". Example: {example}"
    return line


def _format_property(
    spec: dict, name: str, prop: dict, req_marker: str, indent: int = 0
) -> str:
    prefix = " " * indent + f"- {name} ({req_marker})"
    ref = prop.get("$ref")
    if ref:
        resolved = _resolve_ref(spec, ref)
        if resolved and resolved.get("type") == "object" and resolved.get("properties"):
            inner = _format_schema(spec, resolved, indent + 2)
            desc = resolved.get("description", prop.get("description", ""))
            header = prefix + f": {_ref_name(ref)}"
            if desc:
                header += f" — {desc}"
            return header + "\n" + inner
        if resolved:
            inner = _format_schema(spec, resolved, indent + 2)
            return prefix + ": " + inner.strip()

    prop_type = prop.get("type", "any")
    desc = prop.get("description", "")
    enum_vals = prop.get("enum")

    if prop_type == "object" and prop.get("properties"):
        inner = _format_schema(spec, prop, indent + 2)
        header = prefix
        if desc:
            header += f" — {desc}"
        return header + "\n" + inner

    if prop_type == "array":
        items = prop.get("items", {})
        item_ref = items.get("$ref")
        if item_ref:
            resolved = _resolve_ref(spec, item_ref)
            if resolved and resolved.get("type") == "object" and resolved.get("properties"):
                inner = _format_schema(spec, resolved, indent + 2)
                header = prefix + f": Array of {_ref_name(item_ref)}"
                if desc:
                    header += f" — {desc}"
                return header + "\n" + inner
        return prefix + f": Array — {desc}" if desc else prefix + ": Array"

    line = prefix + f": {prop_type}"
    if desc:
        line += f" — {desc}"
    if enum_vals:
        line += f". Enum: {', '.join(str(v) for v in enum_vals)}"
    example = prop.get("example")
    if example is not None:
        line += f". Example: {example}"
    return line


def _format_params(spec: dict, params: list[dict]) -> str:
    lines = []
    for p in params:
        name = p.get("name", "")
        location = p.get("in", "")
        req = "required" if p.get("required") else "optional"
        desc = p.get("description", "")
        p_type = p.get("schema", {}).get("type", "any")
        line = f"- {name} ({location}, {req}): {p_type}"
        if desc:
            line += f" — {desc}"
        lines.append(line)
    return "\n".join(lines)


def _format_responses(spec: dict, responses: dict) -> str:
    lines = []
    for code, resp in sorted(responses.items()):
        desc = resp.get("description", "")
        lines.append(f"  {code}: {desc}")
        content = resp.get("content", {})
        for media_type, media_schema in content.items():
            schema = media_schema.get("schema", {})
            formatted = _format_schema(spec, schema, indent=4)
            lines.append(formatted)
    return "\n".join(lines)


def normalize_operation(
    spec: dict, method: str, path: str, operation: dict
) -> OperationDoc:
    method_upper = method.upper()
    doc_id = f"openapi:{method_upper}-{path}"

    summary = operation.get("summary", "")
    description = operation.get("description", "")
    tags = operation.get("tags", [])
    tag = tags[0] if tags else ""
    deprecated = operation.get("deprecated", False)

    parts: list[str] = []

    header = f"{method_upper} {path}"
    if deprecated:
        header += " (DEPRECATED)"
    parts.append(header)
    parts.append("")

    if summary:
        parts.append(f"Summary: {summary}")

    if description:
        parts.append(description)

    params = operation.get("parameters", [])
    if params:
        parts.append("")
        parts.append("Parameters:")
        parts.append(_format_params(spec, params))

    request_body = operation.get("requestBody")
    if request_body:
        parts.append("")
        parts.append("Request body:")
        req_desc = request_body.get("description", "")
        if req_desc:
            parts.append(f"  {req_desc}")
        content = request_body.get("content", {})
        for media_type, media_schema in content.items():
            schema = media_schema.get("schema", {})
            required = set(schema.get("required", []))
            formatted = _format_schema(spec, schema, indent=2, required_fields=required)
            parts.append(formatted)

    responses = operation.get("responses", {})
    if responses:
        parts.append("")
        parts.append("Responses:")
        parts.append(_format_responses(spec, responses))

    text = "\n".join(parts)
    return OperationDoc(
        doc_id=doc_id,
        method=method_upper,
        path=path,
        tag=tag,
        summary=summary,
        description=description,
        text=text,
    )


def parse_spec(spec_path: str) -> list[OperationDoc]:
    with open(spec_path, encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    docs: list[OperationDoc] = []
    paths = spec.get("paths", {})

    for path, methods in paths.items():
        for method, operation in methods.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            if not isinstance(operation, dict):
                continue
            doc = normalize_operation(spec, method, path, operation)
            docs.append(doc)

    return docs
