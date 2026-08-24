"""Versioned modeling artifact helpers. Binary models are not stored in Firestore."""

from app.modeling.mmm.contracts import MeridianModelArtifactManifest
from app.modeling.mmm.ledger import BQ_MODEL_LEDGER_TABLES

CANONICAL_MODEL_BINARY_NAME = "meridian_model.binpb"

__all__ = [
    "BQ_MODEL_LEDGER_TABLES",
    "CANONICAL_MODEL_BINARY_NAME",
    "MeridianModelArtifactManifest",
]
