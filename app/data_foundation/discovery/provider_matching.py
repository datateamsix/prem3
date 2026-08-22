"""Deterministic registry matching. An LLM cannot declare provider identity."""

from __future__ import annotations

from app.data_foundation.contracts import ProviderMatchEvidence
from app.data_foundation.enums import ProvenanceClass
from app.registry.loader import load_registry
from app.registry.schema import ProviderRegistryEntry


def _normalize(value: str) -> str:
    return "".join(char for char in value.lower() if char.isalnum())


def match_provider(
    *,
    table_or_file_name: str,
    field_names: tuple[str, ...] = (),
    filename_hint: str | None = None,
    requirement_concept: str | None = None,
) -> ProviderMatchEvidence:
    catalog = load_registry()
    best: tuple[float, ProviderRegistryEntry, list[str]] | None = None
    needles = [
        _normalize(table_or_file_name),
        _normalize(filename_hint or ""),
        _normalize(requirement_concept or ""),
    ]
    fields = {_normalize(item) for item in field_names}
    for entry in catalog.providers:
        signals: list[str] = []
        score = 0.0
        identity = {_normalize(entry.provider_id), _normalize(entry.display_name)}
        identity.update(_normalize(hint) for hint in entry.filename_hints)
        extra = [_normalize(item) for item in getattr(entry, "discovery_signatures", []) or []]
        identity.update(extra)
        for needle in needles:
            if needle and any(needle in token or token in needle for token in identity if token):
                score += 0.45
                signals.append(f"name:{entry.provider_id}")
                break
        expected = {_normalize(field.source_name) for field in entry.fields}
        expected.update(_normalize(item) for item in entry.date_fields)
        overlap = fields & expected
        if overlap:
            score += min(0.45, 0.08 * len(overlap))
            signals.append(f"fields:{len(overlap)}")
        if requirement_concept:
            concept = _normalize(requirement_concept)
            category = _normalize(entry.category.value)
            if concept and (concept in category or category in concept):
                score += 0.15
                signals.append("category")
        if best is None or score > best[0]:
            best = (score, entry, signals)
    if best is None or best[0] < 0.35:
        return ProviderMatchEvidence(
            provider_id=None,
            registry_version=catalog.version,
            score=best[0] if best else 0.0,
            signals=tuple(best[2]) if best else (),
            provenance=ProvenanceClass.UNKNOWN,
        )
    provenance = ProvenanceClass.DETECTED if best[0] < 0.75 else ProvenanceClass.VERIFIED
    return ProviderMatchEvidence(
        provider_id=best[1].provider_id,
        registry_version=catalog.version,
        score=round(best[0], 3),
        signals=tuple(best[2]),
        provenance=provenance,
    )
