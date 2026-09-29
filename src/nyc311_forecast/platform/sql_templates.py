"""Render catalog/schema placeholders without accepting arbitrary SQL identifiers."""

from pathlib import Path

from nyc311_forecast.config import IDENTIFIER


def render_sql(path: Path, *, catalog: str, schema: str) -> str:
    if not IDENTIFIER.fullmatch(catalog) or not IDENTIFIER.fullmatch(schema):
        raise ValueError("Unsafe catalog or schema identifier")
    content = Path(path).read_text(encoding="utf-8")
    result = content.replace("{{catalog}}", catalog).replace("{{schema}}", schema)
    if "{{" in result or "}}" in result:
        raise ValueError("Unresolved SQL template token")
    return result
