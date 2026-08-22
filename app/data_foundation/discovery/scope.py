"""Source scope / geography with ranked provenance."""

from __future__ import annotations

from app.data_foundation.contracts import SourceScope
from app.data_foundation.enums import ScopeProvenance


def infer_source_scope(
    *,
    field_names: tuple[str, ...],
    geo_field: str | None,
    markets: tuple[str, ...] = (),
    filename: str | None = None,
    user_scope: SourceScope | None = None,
) -> SourceScope:
    if user_scope is not None and user_scope.market_scope:
        return user_scope.model_copy(update={"provenance": ScopeProvenance.USER_PROVIDED})
    if geo_field and geo_field in field_names:
        return SourceScope(
            market_scope=markets,
            geo_level="field",
            geo_field=geo_field,
            geo_values_summary=geo_field,
            provenance=ScopeProvenance.SCHEMA_DETECTED,
        )
    geo_columns = [name for name in field_names if name.lower() in {"geo", "country", "region", "dma", "market"}]
    if geo_columns:
        return SourceScope(
            market_scope=markets,
            geo_level="column",
            geo_field=geo_columns[0],
            geo_values_summary=geo_columns[0],
            provenance=ScopeProvenance.PROFILE_DETECTED,
        )
    if markets:
        return SourceScope(
            market_scope=markets,
            geo_level="business_profile",
            provenance=ScopeProvenance.BUSINESS_IQ_INFERRED,
        )
    if filename:
        lowered = filename.lower()
        guessed = None
        for token in ("us", "uk", "eu", "national"):
            if token in lowered:
                guessed = token
                break
        if guessed:
            return SourceScope(
                market_scope=(guessed,),
                geo_level="filename",
                geo_values_summary=guessed,
                provenance=ScopeProvenance.FILENAME_INFERRED,
                filename_inferred=True,
                filename_has_authority=False,
            )
    return SourceScope(provenance=ScopeProvenance.UNKNOWN)
