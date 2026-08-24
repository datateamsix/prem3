"""Classify worker/runtime failures. No silent fake fallback."""

from __future__ import annotations

from app.modeling.common.errors import (
    FitRuntimeError,
    GcsPersistenceError,
    GpuNotVisibleError,
    InputContractMismatchError,
    LedgerPublicationError,
    MeridianImportError,
    ModelingError,
    ModelReviewFailedError,
    PriorValidationFailedError,
    ResourceExhaustedError,
    SerdeError,
)

FAILURE_CLASSES = (
    "MERIDIAN_IMPORT_FAILED",
    "GPU_NOT_VISIBLE",
    "INPUT_CONTRACT_MISMATCH",
    "PRIOR_VALIDATION_FAILED",
    "FIT_RUNTIME_ERROR",
    "RESOURCE_EXHAUSTED",
    "SERDE_ERROR",
    "MODEL_REVIEW_FAILED",
    "GCS_PERSISTENCE_FAILED",
    "FIRESTORE_PERSISTENCE_FAILED",
    "BQ_LEDGER_FAILED",
)


def classify_failure(exc: BaseException) -> str:
    if isinstance(exc, ModelingError) and getattr(exc, "code", None):
        mapping = {
            "MERIDIAN_IMPORT_FAILED": "MERIDIAN_IMPORT_FAILED",
            "GPU_NOT_VISIBLE": "GPU_NOT_VISIBLE",
            "INPUT_CONTRACT_MISMATCH": "INPUT_CONTRACT_MISMATCH",
            "PRIOR_VALIDATION_FAILED": "PRIOR_VALIDATION_FAILED",
            "FIT_RUNTIME_ERROR": "FIT_RUNTIME_ERROR",
            "RESOURCE_EXHAUSTED": "RESOURCE_EXHAUSTED",
            "SERDE_ERROR": "SERDE_ERROR",
            "MODEL_REVIEW_FAILED": "MODEL_REVIEW_FAILED",
            "GCS_PERSISTENCE_FAILED": "GCS_PERSISTENCE_FAILED",
            "FIRESTORE_PERSISTENCE_FAILED": "FIRESTORE_PERSISTENCE_FAILED",
            "LEDGER_PUBLICATION_FAILED": "BQ_LEDGER_FAILED",
        }
        return mapping.get(exc.code, "FIT_RUNTIME_ERROR")
    if isinstance(exc, MeridianImportError):
        return "MERIDIAN_IMPORT_FAILED"
    if isinstance(exc, GpuNotVisibleError):
        return "GPU_NOT_VISIBLE"
    if isinstance(exc, InputContractMismatchError):
        return "INPUT_CONTRACT_MISMATCH"
    if isinstance(exc, PriorValidationFailedError):
        return "PRIOR_VALIDATION_FAILED"
    if isinstance(exc, ResourceExhaustedError):
        return "RESOURCE_EXHAUSTED"
    if isinstance(exc, SerdeError):
        return "SERDE_ERROR"
    if isinstance(exc, ModelReviewFailedError):
        return "MODEL_REVIEW_FAILED"
    if isinstance(exc, GcsPersistenceError):
        return "GCS_PERSISTENCE_FAILED"
    if isinstance(exc, LedgerPublicationError):
        return "BQ_LEDGER_FAILED"
    if isinstance(exc, FitRuntimeError):
        return "FIT_RUNTIME_ERROR"
    text = str(exc).lower()
    if "resource exhausted" in text or "out of memory" in text or "oom" in text:
        return "RESOURCE_EXHAUSTED"
    return "FIT_RUNTIME_ERROR"
