"""Render sql/mta/*.sql.j2 templates with server-owned parameters."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import BaseLoader, Environment, StrictUndefined

from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mta.sql.registry import SqlAssetEntry, resolve_asset_path


class _StringLoader(BaseLoader):
    def __init__(self, mapping: dict[str, str]) -> None:
        self.mapping = mapping

    def get_source(self, environment: Environment, template: str):
        source = self.mapping[template]
        return source, None, lambda: True


def render_sql_template(
    template_text: str,
    *,
    params: dict[str, Any],
    template_name: str = "inline",
) -> str:
    """Deterministic Jinja render — no LLM, StrictUndefined."""
    env = Environment(
        loader=_StringLoader({template_name: template_text}),
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
    )
    return env.get_template(template_name).render(**params)


def render_sql_asset(
    entry: SqlAssetEntry,
    *,
    params: dict[str, Any],
    path: Path | None = None,
) -> tuple[str, str]:
    """Return (rendered_sql, sql_fingerprint)."""
    text = (path or resolve_asset_path(entry)).read_text(encoding="utf-8")
    rendered = render_sql_template(text, params=params, template_name=entry.asset_id)
    fingerprint = canonical_fingerprint(
        {
            "asset_id": entry.asset_id,
            "path": entry.path,
            "params": params,
            "sql": rendered,
        }
    )
    return rendered, fingerprint
