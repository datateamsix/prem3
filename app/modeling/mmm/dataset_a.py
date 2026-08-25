"""Music Center Dataset A ModelReady frame for official FINAL_MODEL.

The worker image copies the verified weekly CSV. Fingerprint identity stays
the canonical Dataset A digest; the ModelPlan fingerprint may be the Music
Center model-ready identity used by existing M3 plans.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from app.modeling.common.errors import FitRuntimeError
from app.modeling.mmm.contracts import ModelPlan
from app.modeling.mmm.coverage import MUSIC_CENTER_MODEL_READY_COVERAGE

# Keep in lockstep with app.eda.music_center. Modeling worker must not import EDA.
MUSIC_CENTER_DATASET_FINGERPRINT = (
    "7cfc15152067923b6ec6d2b77d6b4e4fae16b748eae24deb250939e7458fe18f"
)
MUSIC_CENTER_MODEL_READY_FINGERPRINT = "mc-q3-2026-model-ready-fingerprint"

DATASET_A_CSV_RELATIVE = Path(
    "datasets/music_center/dataset_a/truth/expected_model_ready_weekly.csv"
)
PACKAGED_DATASET_A_CSV = Path("/app") / DATASET_A_CSV_RELATIVE
REPO_DATASET_A_CSV = Path(__file__).resolve().parents[3] / DATASET_A_CSV_RELATIVE

MUSIC_CENTER_FINAL_FINGERPRINTS = frozenset(
    {
        MUSIC_CENTER_DATASET_FINGERPRINT,
        MUSIC_CENTER_MODEL_READY_FINGERPRINT,
    }
)


def dataset_a_csv_path() -> Path:
    if PACKAGED_DATASET_A_CSV.is_file():
        return PACKAGED_DATASET_A_CSV
    if REPO_DATASET_A_CSV.is_file():
        return REPO_DATASET_A_CSV
    raise FitRuntimeError("INPUT_CONTRACT_MISMATCH: Dataset A ModelReady CSV is missing.")


def music_center_dataset_a_mapping(plan: ModelPlan) -> dict[str, Any]:
    fingerprint = plan.model_ready_manifest_fingerprint
    if fingerprint not in MUSIC_CENTER_FINAL_FINGERPRINTS:
        raise FitRuntimeError("INPUT_CONTRACT_MISMATCH: ModelReady frame is missing.")
    frame = pd.read_csv(dataset_a_csv_path())
    frame["time"] = pd.to_datetime(frame["time"])
    start = pd.Timestamp(plan.model_window_start)
    end = pd.Timestamp(plan.model_window_end)
    windowed = frame.loc[(frame["time"] >= start) & (frame["time"] <= end)].copy()
    geos = tuple(sorted(str(item) for item in windowed["geo"].unique()))
    n_times = int(windowed["time"].nunique())
    if n_times != (MUSIC_CENTER_MODEL_READY_COVERAGE.n_times or 0):
        raise FitRuntimeError(
            "INPUT_CONTRACT_MISMATCH: Dataset A windowed n_times does not match coverage."
        )
    if geos != tuple(MUSIC_CENTER_MODEL_READY_COVERAGE.geos or ()):
        raise FitRuntimeError(
            "INPUT_CONTRACT_MISMATCH: Dataset A geos do not match coverage."
        )
    return {
        "fingerprint": fingerprint,
        "dataset_a_fingerprint": MUSIC_CENTER_DATASET_FINGERPRINT,
        "frame": windowed,
        "kpi": "kpi_revenue",
        "kpi_type": "revenue",
        "time": "time",
        "geo": "geo",
        "population": "population",
        "media": (
            "paid_search_impressions",
            "shopping_impressions",
            "paid_social_impressions",
        ),
        "media_spend": (
            "paid_search_spend",
            "shopping_spend",
            "paid_social_spend",
        ),
        "media_channels": ("paid_search", "shopping", "paid_social"),
        "organic_media": ("organic_sessions",),
        "organic_media_channels": ("organic_sessions",),
        "controls": (
            "consumer_sentiment_index",
            "competitor_discount_index",
        ),
        "non_media_treatments": ("music_center_promo",),
        "n_times": n_times,
        "n_geos": len(geos),
        "source": str(DATASET_A_CSV_RELATIVE).replace("\\", "/"),
    }
