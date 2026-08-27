"""Deterministic overlap exclusion. Never silent UNION of master + regional."""

from __future__ import annotations

from app.identity_graph.contracts import GA4PropertySourceBinding
from app.identity_graph.enums import (
    GA4TopologyKind,
    OverlapCompileStatus,
    SourceOverlapPolicy,
)

EXCLUSION_SQL = {
    SourceOverlapPolicy.DISJOINT: "sql/identity_graph/overlap/disjoint_union.sql.j2",
    SourceOverlapPolicy.MASTER_AUTHORITATIVE: (
        "sql/identity_graph/overlap/master_authoritative.sql.j2"
    ),
    SourceOverlapPolicy.REGIONAL_AUTHORITATIVE: (
        "sql/identity_graph/overlap/regional_authoritative.sql.j2"
    ),
    SourceOverlapPolicy.PARTITIONED_BY_MARKET: (
        "sql/identity_graph/overlap/partitioned_by_market.sql.j2"
    ),
}


def overlap_compile_status(
    *,
    topology_kind: GA4TopologyKind,
    overlap_policy: SourceOverlapPolicy | None,
) -> tuple[OverlapCompileStatus, tuple[str, ...]]:
    issues: list[str] = []
    if topology_kind == GA4TopologyKind.MASTER_PLUS_REGIONAL and overlap_policy is None:
        issues.append("OVERLAP_POLICY_REQUIRED")
        return OverlapCompileStatus.OVERLAP_POLICY_REQUIRED, tuple(issues)
    if overlap_policy is None:
        if topology_kind in {
            GA4TopologyKind.PROPERTY_PER_MARKET,
            GA4TopologyKind.SINGLE_MASTER_PROPERTY,
        }:
            return OverlapCompileStatus.DISJOINT, ()
        issues.append("OVERLAP_POLICY_REQUIRED")
        return OverlapCompileStatus.OVERLAP_POLICY_REQUIRED, tuple(issues)
    if overlap_policy == SourceOverlapPolicy.DEDUPE_REQUIRED:
        issues.extend(("DEDUPE_POLICY_REQUIRED", "DEDUPE_REQUIRED_NOT_ANALYTICALLY_READY"))
        return OverlapCompileStatus.DEDUPE_REQUIRED_NOT_ANALYTICALLY_READY, tuple(issues)
    if overlap_policy == SourceOverlapPolicy.REVIEW_REQUIRED:
        issues.append("OVERLAP_REVIEW_REQUIRED")
        return OverlapCompileStatus.REVIEW_REQUIRED, tuple(issues)
    mapping = {
        SourceOverlapPolicy.DISJOINT: OverlapCompileStatus.DISJOINT,
        SourceOverlapPolicy.MASTER_AUTHORITATIVE: OverlapCompileStatus.MASTER_AUTHORITATIVE,
        SourceOverlapPolicy.REGIONAL_AUTHORITATIVE: OverlapCompileStatus.REGIONAL_AUTHORITATIVE,
        SourceOverlapPolicy.PARTITIONED_BY_MARKET: OverlapCompileStatus.PARTITIONED_BY_MARKET,
    }
    return mapping[overlap_policy], ()


def exclusion_template(overlap_policy: SourceOverlapPolicy | None) -> str | None:
    if overlap_policy is None:
        return EXCLUSION_SQL[SourceOverlapPolicy.DISJOINT]
    return EXCLUSION_SQL.get(overlap_policy)


def apply_overlap_filter(
    *,
    seeds: tuple,
    sources: tuple[GA4PropertySourceBinding, ...],
    overlap_policy: SourceOverlapPolicy | None,
) -> tuple:
    """In-memory analogue of the documented exclusion SQL. No person stitching."""
    if not seeds:
        return ()
    by_binding = {item.ga4_source_binding_id: item for item in sources}
    if overlap_policy in {None, SourceOverlapPolicy.DISJOINT}:
        return seeds
    ordered = tuple(item.ga4_source_binding_id for item in sources)
    if not ordered:
        return seeds
    master_id = ordered[0]
    regional_ids = set(ordered[1:])
    if overlap_policy == SourceOverlapPolicy.MASTER_AUTHORITATIVE:
        master_keys = {
            (item.subject_key, item.ga_session_id)
            for item in seeds
            if item.ga4_source_binding_id == master_id
        }
        kept = []
        for item in seeds:
            if item.ga4_source_binding_id == master_id:
                kept.append(item)
            elif item.ga4_source_binding_id in regional_ids:
                if (item.subject_key, item.ga_session_id) not in master_keys:
                    kept.append(item)
        return tuple(kept)
    if overlap_policy == SourceOverlapPolicy.REGIONAL_AUTHORITATIVE:
        regional_keys = {
            (item.subject_key, item.ga_session_id)
            for item in seeds
            if item.ga4_source_binding_id in regional_ids
        }
        kept = []
        for item in seeds:
            if item.ga4_source_binding_id in regional_ids:
                kept.append(item)
            elif item.ga4_source_binding_id == master_id:
                if (item.subject_key, item.ga_session_id) not in regional_keys:
                    kept.append(item)
        return tuple(kept)
    if overlap_policy == SourceOverlapPolicy.PARTITIONED_BY_MARKET:
        kept = []
        for item in seeds:
            source = by_binding.get(item.ga4_source_binding_id)
            if source is None:
                continue
            kept.append(item)
        return tuple(kept)
    return seeds
