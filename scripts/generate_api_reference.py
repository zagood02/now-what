from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

DEFAULT_OUTPUT_PATH = ROOT_DIR / "docs" / "api-reference.md"
METHOD_ORDER = {"get": 0, "post": 1, "patch": 2, "put": 3, "delete": 4}
SUCCESS_STATUS_CODES = ("200", "201", "202", "204")


@dataclass(frozen=True)
class Endpoint:
    tag: str
    method: str
    path: str
    summary: str
    auth: str
    parameters: list[dict[str, Any]]
    request_schema: str
    response_schema: str
    status_codes: list[str]


def schema_label(schema: dict[str, Any] | bool | None) -> str:
    if not schema:
        return "-"
    if schema is True:
        return "`Any`"

    if "$ref" in schema:
        return f"`{schema['$ref'].rsplit('/', 1)[-1]}`"

    if "allOf" in schema:
        labels = [schema_label(item).strip("`") for item in schema["allOf"]]
        return f"`{' / '.join(label for label in labels if label)}`"

    if "anyOf" in schema:
        labels = [schema_label(item).strip("`") for item in schema["anyOf"]]
        return f"`{' or '.join(label for label in labels if label and label != '-')}`"

    if "items" in schema:
        return f"`list[{schema_label(schema['items']).strip('`')}]`"

    schema_type = schema.get("type")
    if schema_type == "object" and "additionalProperties" in schema:
        value_type = schema_label(schema["additionalProperties"]).strip("`")
        return f"`dict[str, {value_type}]`"

    if schema_type:
        return f"`{schema_type}`"

    title = schema.get("title")
    return f"`{title}`" if title else "-"


def json_body_schema(operation: dict[str, Any]) -> str:
    request_body = operation.get("requestBody")
    if not request_body:
        return "-"
    content = request_body.get("content", {})
    json_content = content.get("application/json", {})
    return schema_label(json_content.get("schema"))


def response_schema(operation: dict[str, Any]) -> str:
    responses = operation.get("responses", {})
    for status_code in SUCCESS_STATUS_CODES:
        response = responses.get(status_code)
        if not response:
            continue
        content = response.get("content", {})
        json_content = content.get("application/json", {})
        return schema_label(json_content.get("schema"))
    return "-"


def auth_label(operation: dict[str, Any]) -> str:
    security = operation.get("security") or []
    if any("HTTPBearer" in item for item in security):
        return "Required"
    return "Public"


def parameter_label(parameter: dict[str, Any]) -> str:
    required = "required" if parameter.get("required") else "optional"
    param_type = schema_label(parameter.get("schema")).strip("`")
    return f"`{parameter['name']}` ({parameter['in']}, {required}, {param_type})"


def collect_endpoints(schema: dict[str, Any]) -> list[Endpoint]:
    endpoints: list[Endpoint] = []
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            tag = (operation.get("tags") or ["untagged"])[0]
            status_codes = sorted(
                code
                for code in operation.get("responses", {})
                if code != "422"
            )
            endpoints.append(
                Endpoint(
                    tag=tag,
                    method=method.upper(),
                    path=path,
                    summary=operation.get("summary") or operation.get("operationId") or "",
                    auth=auth_label(operation),
                    parameters=operation.get("parameters") or [],
                    request_schema=json_body_schema(operation),
                    response_schema=response_schema(operation),
                    status_codes=status_codes,
                )
            )
    return sorted(
        endpoints,
        key=lambda item: (
            item.tag,
            item.path,
            METHOD_ORDER.get(item.method.lower(), 99),
        ),
    )


def collect_referenced_schema_names(endpoints: list[Endpoint]) -> set[str]:
    referenced: set[str] = set()
    for endpoint in endpoints:
        for label in (endpoint.request_schema, endpoint.response_schema):
            for raw in label.replace("`", "").replace("list[", "").replace("]", "").split(" or "):
                name = raw.strip()
                if name and name not in {"-", "object", "string", "integer", "number", "boolean"}:
                    referenced.add(name)
    return referenced


def render_schema_details(schema_name: str, schema: dict[str, Any]) -> list[str]:
    lines = [f"### `{schema_name}`", ""]
    properties = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    if not properties:
        lines.extend(["No properties listed.", ""])
        return lines

    lines.extend(["| Field | Type | Required |", "| --- | --- | --- |"])
    for field_name, field_schema in properties.items():
        required_label = "yes" if field_name in required else "no"
        lines.append(f"| `{field_name}` | {schema_label(field_schema)} | {required_label} |")
    lines.append("")
    return lines


def render_markdown(schema: dict[str, Any]) -> str:
    info = schema.get("info", {})
    endpoints = collect_endpoints(schema)
    grouped: dict[str, list[Endpoint]] = defaultdict(list)
    for endpoint in endpoints:
        grouped[endpoint.tag].append(endpoint)

    lines = [
        "# API Reference",
        "",
        "<!-- This file is generated by scripts/generate_api_reference.py. -->",
        "",
        f"OpenAPI version: `{schema.get('openapi', '-')}`",
        f"API title: `{info.get('title', '-')}`",
        f"API version: `{info.get('version', '-')}`",
        "",
        "Base URL examples:",
        "",
        "- `http://127.0.0.1:8000/api/v1`",
        "- `http://localhost:8000/api/v1`",
        "",
        "Authentication:",
        "",
        "- Endpoints marked `Required` expect `Authorization: Bearer <access_token>`.",
        "- `422` validation responses are omitted from the status column to keep the table readable.",
        "",
        "## Endpoints",
        "",
    ]

    for tag in sorted(grouped):
        lines.extend([f"### {tag}", ""])
        lines.extend(
            [
                "| Method | Path | Auth | Request | Response | Status | Summary |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for endpoint in grouped[tag]:
            statuses = ", ".join(f"`{status}`" for status in endpoint.status_codes) or "-"
            lines.append(
                f"| `{endpoint.method}` | `{endpoint.path}` | {endpoint.auth} | "
                f"{endpoint.request_schema} | {endpoint.response_schema} | {statuses} | "
                f"{endpoint.summary} |"
            )
        lines.append("")

        parameter_lines = []
        for endpoint in grouped[tag]:
            if endpoint.parameters:
                joined = "<br>".join(parameter_label(parameter) for parameter in endpoint.parameters)
                parameter_lines.append(f"- `{endpoint.method} {endpoint.path}`: {joined}")
        if parameter_lines:
            lines.extend(["Parameters:", ""])
            lines.extend(parameter_lines)
            lines.append("")

    components = schema.get("components", {}).get("schemas", {})
    referenced = collect_referenced_schema_names(endpoints)
    schema_names = [name for name in sorted(components) if name in referenced]
    if schema_names:
        lines.extend(["## Referenced Schemas", ""])
        for schema_name in schema_names:
            lines.extend(render_schema_details(schema_name, components[schema_name]))

    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Markdown API reference from FastAPI OpenAPI schema.")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help=f"Output Markdown path. Default: {DEFAULT_OUTPUT_PATH}",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write; fail if the generated reference differs from the output file.",
    )
    return parser.parse_args()


def main() -> int:
    from backend.main import app

    args = parse_args()
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = ROOT_DIR / output_path

    content = render_markdown(app.openapi())

    if args.check:
        existing = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
        if existing != content:
            print(f"[FAIL] API reference is stale: {output_path}")
            print("Run:")
            print(f"  .\\.venv\\Scripts\\python.exe scripts\\generate_api_reference.py --output {output_path}")
            return 1
        print(f"[OK] API reference is up to date: {output_path}")
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"[OK] Generated API reference: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
