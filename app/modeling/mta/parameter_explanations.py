"""Load model/parameter explanation metadata from assets/mta/model_registry_v1.yaml."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.domain.channels.registry import repo_root


def model_registry_path() -> Path:
    return repo_root() / "assets" / "mta" / "model_registry_v1.yaml"


@lru_cache(maxsize=1)
def load_model_registry() -> dict[str, Any]:
    return yaml.safe_load(model_registry_path().read_text(encoding="utf-8"))


LOOKBACK_EXPLANATION = (
    "Number of days before conversion used to assemble eligible touchpoints. "
    "Changes the journey evidence window and must be fingerprinted."
)


def parameter_explanations() -> dict[str, str]:
    """Concise explanations for API/read models — no frontend hardcoding required."""
    registry = load_model_registry()
    out: dict[str, str] = {
        "lookback_window_days": LOOKBACK_EXPLANATION,
    }
    for model in registry.get("models", []):
        model_id = str(model["id"])
        for param in model.get("parameters") or []:
            key = f"{model_id}.{param['id']}"
            explanation = param.get("explanation") or param.get("id")
            out[key] = str(explanation)
        # Friendly aliases used in mission §40
        if model_id == "TIME_DECAY":
            out.setdefault(
                "TIME_DECAY.decay_over_time",
                out.get("TIME_DECAY.decay_over_time", ""),
            )
            out.setdefault("TIME_DECAY.frequency", out.get("TIME_DECAY.frequency", ""))
        if model_id == "POSITION_BASED":
            out["POSITION_BASED.weights"] = (
                "first_weight + middle_weight + last_weight must equal 1.0; "
                "allocates observable credit by journey position."
            )
    return out


def list_model_explanations() -> list[dict[str, Any]]:
    registry = load_model_registry()
    return [
        {
            "model_id": m["id"],
            "display_name": m.get("display_name"),
            "explanation": m.get("explanation"),
            "configurable": bool(m.get("configurable")),
            "parameters": list(m.get("parameters") or []),
        }
        for m in registry.get("models", [])
    ]
