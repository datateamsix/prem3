"""Fingerprinted IG-04 SQL templates. New files under sql/identity_graph/; do not mutate sql/mta."""

from __future__ import annotations

from pathlib import Path

from app.domain.channels.registry import repo_root
from app.identity_graph.fingerprint import identity_fingerprint
from app.modeling.mta.contracts import SessionTrafficSourcePolicy

TEMPLATE_ROOT = "sql/identity_graph"

SESSION_TEMPLATES = {
    SessionTrafficSourcePolicy.GA4_SESSION_LAST_CLICK_V1: (
        "sessions/ga4_sessions_unified_last_click_v1.sql.j2"
    ),
    SessionTrafficSourcePolicy.FIRST_VALID_COLLECTED_SOURCE_V1: (
        "sessions/ga4_sessions_unified_collected_fallback_v1.sql.j2"
    ),
}


def sql_root() -> Path:
    return repo_root() / TEMPLATE_ROOT


def read_template(relative: str) -> str:
    return (sql_root() / relative).read_text(encoding="utf-8")


def sql_plan_fingerprint(
    *,
    session_policy: SessionTrafficSourcePolicy,
    overlap_template: str | None,
) -> str:
    parts: dict[str, str] = {}
    relative = SESSION_TEMPLATES.get(
        session_policy, SESSION_TEMPLATES[SessionTrafficSourcePolicy.GA4_SESSION_LAST_CLICK_V1]
    )
    parts["session"] = read_template(relative)
    parts["touchpoints"] = read_template("touchpoints/mta_session_touchpoints_v1.sql.j2")
    parts["journeys"] = read_template("journeys/mta_journeys_v1.sql.j2")
    parts["ddl"] = read_template("ddl/create_compilation_tables_v1.sql.j2")
    if overlap_template is not None:
        overlap_path = repo_root() / overlap_template
        parts["overlap"] = overlap_path.read_text(encoding="utf-8")
    return identity_fingerprint(parts)
