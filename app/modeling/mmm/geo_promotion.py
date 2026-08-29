"""Governed geo-varying promotion evidence. Never manufacture variation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from app.modeling.common.errors import FabricatedGeoVariationError
from app.modeling.mmm.contracts import (
    GeoPromotionEvidenceStatus,
    PromotionProvenance,
)
from app.modeling.mmm.dataset_a import DATASET_A_CSV_RELATIVE, dataset_a_csv_path
from app.modeling.mmm.identifiability import MUSIC_CENTER_PROMO_VARIABLE

REPO_ROOT = Path(__file__).resolve().parents[3]
DATASET_A_RAW = REPO_ROOT / "datasets" / "music_center" / "dataset_a" / "raw"
DATASET_B_RAW = REPO_ROOT / "datasets" / "music_center" / "dataset_b" / "raw"
CONTROLS_A = DATASET_A_RAW / "controls_weekly.csv"
CONTROLS_B = DATASET_B_RAW / "controls_weekly.csv"
MODEL_INTENT_A = DATASET_A_RAW / "model_intent.json"

_GEO_PROMOTION_HINTS = (
    "regional_promo",
    "geo_promo",
    "promo_intensity",
    "discount_depth",
    "offer_eligibility",
    "store_participation",
    "campaign_intensity",
    "promotion_spend",
)


def _variation(frame: pd.DataFrame, column: str) -> dict[str, Any]:
    time_col = "time" if "time" in frame.columns else "week_start"
    geo_col = "geo" if "geo" in frame.columns else None
    if column not in frame.columns or time_col not in frame.columns or geo_col is None:
        return {
            "present": False,
            "geo_variation": False,
            "time_variation": False,
            "geo_invariant_times": 0,
            "n_times": 0,
        }
    geos = frame.groupby(time_col)[column].nunique(dropna=False)
    n_times = int(len(geos))
    invariant = int((geos <= 1).sum())
    time_variation = bool(frame.groupby(geo_col)[column].nunique(dropna=False).max() > 1)
    return {
        "present": True,
        "geo_variation": bool(invariant < n_times),
        "time_variation": time_variation,
        "geo_invariant_times": invariant,
        "n_times": n_times,
    }


def _source_has_geo_promotion_hint(path: Path) -> bool:
    if not path.is_file():
        return False
    payload = json.loads(path.read_text(encoding="utf-8"))
    blob = json.dumps(payload).lower()
    return any(hint in blob for hint in _GEO_PROMOTION_HINTS)


def inspect_music_center_promotion_evidence() -> dict[str, Any]:
    """Server-owned C eligibility. ModelReady absence is not the whole universe."""

    model_ready = _variation(pd.read_csv(dataset_a_csv_path()), MUSIC_CENTER_PROMO_VARIABLE)
    source_a = (
        _variation(pd.read_csv(CONTROLS_A), MUSIC_CENTER_PROMO_VARIABLE)
        if CONTROLS_A.is_file()
        else {"present": False, "geo_variation": False, "time_variation": False}
    )
    source_b = (
        _variation(pd.read_csv(CONTROLS_B), MUSIC_CENTER_PROMO_VARIABLE)
        if CONTROLS_B.is_file()
        else {"present": False, "geo_variation": False, "time_variation": False}
    )
    intent_hints = _source_has_geo_promotion_hint(MODEL_INTENT_A)
    genuine = bool(
        model_ready.get("geo_variation")
        or source_a.get("geo_variation")
        or source_b.get("geo_variation")
        or intent_hints
    )
    inspected = bool(CONTROLS_A.is_file() or CONTROLS_B.is_file() or MODEL_INTENT_A.is_file())
    if genuine:
        status = GeoPromotionEvidenceStatus.GEO_PROMOTION_EVIDENCE_AVAILABLE
        available = True
        reason = None
    elif inspected:
        status = GeoPromotionEvidenceStatus.GEO_PROMOTION_EVIDENCE_NOT_FOUND
        available = False
        reason = (
            "Governed source inventory and ModelReady both lack a geo-varying "
            "promotion intensity measure. Alternative C is not eligible."
        )
    else:
        status = GeoPromotionEvidenceStatus.GEO_PROMOTION_EVIDENCE_UNKNOWN
        available = False
        reason = "Governed source inventory could not be inspected."
    provenance = PromotionProvenance(
        variable=MUSIC_CENTER_PROMO_VARIABLE,
        semantic_role="non_media_treatments",
        source_dataset="music_center/dataset_a",
        source_file=str(DATASET_A_CSV_RELATIVE).replace("\\", "/"),
        source_field=MUSIC_CENTER_PROMO_VARIABLE,
        coverage="2024-01-01/2026-06-29 weekly CA,FL,NY,TX",
        time_variation=bool(model_ready.get("time_variation")),
        geo_variation=bool(model_ready.get("geo_variation")),
        transform_history=(
            "raw/controls_weekly.csv",
            "truth/expected_model_ready_weekly.csv",
        ),
        model_ready_fingerprint=None,
    )
    return {
        "status": status,
        "alternative_c_available": available,
        "unavailable_reason": reason,
        "model_ready": model_ready,
        "source_dataset_a": source_a,
        "source_dataset_b": source_b,
        "intent_geo_promotion_hints": intent_hints,
        "provenance": provenance,
        "inspected_source_universe": inspected,
    }


def refuse_fabricated_geo_variation(payload: dict[str, Any]) -> None:
    forbidden = {
        "random_jitter",
        "synthetic_market_weights",
        "duplicated_national_value",
        "llm_generated_intensity",
        "unsupported_allocation",
        "geo_variation",
        "synthetic_geo_weights",
        "fabricate_geo_variation",
    }
    hits = forbidden.intersection(payload)
    if hits:
        raise FabricatedGeoVariationError(
            "Geo variation in music_center_promo cannot be fabricated: "
            f"{sorted(hits)}."
        )
