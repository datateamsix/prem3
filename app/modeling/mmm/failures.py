"""Classify worker/runtime failures. No silent fake fallback."""

from __future__ import annotations

from dataclasses import dataclass

from app.modeling.common.errors import (
    FitRuntimeError,
    GcsPersistenceError,
    GpuNotVisibleError,
    InputContractMismatchError,
    LedgerPublicationError,
    MeridianImportError,
    ModelingError,
    ModelReviewFailedError,
    ModelSpecIdentifiabilityError,
    ModelSpecInvalidError,
    PriorValidationFailedError,
    ResourceExhaustedError,
    SerdeError,
)
from app.modeling.common.external_assets import PINNED_RUNTIME_VERSION
from app.modeling.mmm.contracts import (
    FitFailureClass,
    FitFailureStage,
    FitNextActionType,
    FitRunStatus,
    RetrySemantics,
)
from app.modeling.mmm.identifiability import (
    OFFICIAL_MERIDIAN_LIBRARY,
    is_geo_invariant_identifiability_error,
    official_identifiability_message,
    prem3_identifiability_summary,
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
    FitFailureClass.MODEL_SPEC_IDENTIFIABILITY_ERROR.value,
    FitFailureClass.SERIALIZATION_ERROR.value,
)

_LEGACY_CODES = {
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
    "MODEL_SPEC_IDENTIFIABILITY_ERROR": (
        FitFailureClass.MODEL_SPEC_IDENTIFIABILITY_ERROR.value
    ),
    "MODEL_SPEC_INVALID": FitFailureClass.MODEL_SPEC_VALIDATION_ERROR.value,
}

TERMINAL_FIT_STATUSES = frozenset(
    {
        FitRunStatus.SUCCEEDED,
        FitRunStatus.COMPLETE,
        FitRunStatus.FAILED,
        FitRunStatus.FAILED_PRE_FIT,
        FitRunStatus.FAILED_RUNTIME,
        FitRunStatus.FAILED_POSTERIOR,
        FitRunStatus.FAILED_REVIEW,
        FitRunStatus.CANCELED,
    }
)

ACTIVE_FIT_STATUSES = frozenset(
    {
        FitRunStatus.PENDING,
        FitRunStatus.QUEUED,
        FitRunStatus.RUNNING,
        FitRunStatus.SUCCEEDED,
        FitRunStatus.COMPLETE,
    }
)


@dataclass(frozen=True)
class FitFailureClassification:
    failure_class: FitFailureClass
    failure_stage: FitFailureStage
    status: FitRunStatus
    retry_semantics: RetrySemantics
    sampling_started: bool
    next_actions: tuple[str, ...]
    library: str | None
    library_version: str | None
    exception_type: str
    official_message: str
    prem3_summary: str | None
    error_code: str

    def to_exception(self) -> ModelingError:
        if self.failure_class is FitFailureClass.MODEL_SPEC_IDENTIFIABILITY_ERROR:
            return ModelSpecIdentifiabilityError(
                self.official_message,
                official_message=self.official_message,
                exception_type=self.exception_type,
            )
        if self.failure_class is FitFailureClass.SERIALIZATION_ERROR:
            return SerdeError(self.official_message)
        if self.failure_class is FitFailureClass.INPUT_CONTRACT_ERROR:
            return InputContractMismatchError(self.official_message)
        if self.failure_class is FitFailureClass.PRIOR_VALIDATION_ERROR:
            return PriorValidationFailedError(self.official_message)
        if self.failure_class is FitFailureClass.RESOURCE_EXHAUSTED:
            return ResourceExhaustedError(self.official_message)
        return FitRuntimeError(self.official_message)


def classify_fit_failure(exc: BaseException) -> FitFailureClassification:
    official = official_identifiability_message(exc) if exc else ""
    exception_type = type(exc).__name__
    if isinstance(exc, ModelSpecIdentifiabilityError) or is_geo_invariant_identifiability_error(
        exc
    ):
        official = getattr(exc, "official_message", None) or official
        exception_type = getattr(exc, "exception_type", None) or exception_type
        return FitFailureClassification(
            failure_class=FitFailureClass.MODEL_SPEC_IDENTIFIABILITY_ERROR,
            failure_stage=FitFailureStage.MODEL_INITIALIZATION,
            status=FitRunStatus.FAILED_PRE_FIT,
            retry_semantics=RetrySemantics.NEW_MODEL_DESIGN_REQUIRED,
            sampling_started=False,
            next_actions=(FitNextActionType.REVIEW_MODEL_IDENTIFIABILITY.value,),
            library=OFFICIAL_MERIDIAN_LIBRARY,
            library_version=PINNED_RUNTIME_VERSION,
            exception_type=exception_type,
            official_message=official,
            prem3_summary=prem3_identifiability_summary(official),
            error_code=FitFailureClass.MODEL_SPEC_IDENTIFIABILITY_ERROR.value,
        )
    if isinstance(exc, ModelSpecInvalidError):
        return FitFailureClassification(
            failure_class=FitFailureClass.MODEL_SPEC_VALIDATION_ERROR,
            failure_stage=FitFailureStage.MODEL_INITIALIZATION,
            status=FitRunStatus.FAILED_PRE_FIT,
            retry_semantics=RetrySemantics.NEW_MODEL_DESIGN_REQUIRED,
            sampling_started=False,
            next_actions=(FitNextActionType.REVIEW_MODEL_SPEC.value,),
            library=OFFICIAL_MERIDIAN_LIBRARY,
            library_version=PINNED_RUNTIME_VERSION,
            exception_type=exception_type,
            official_message=official,
            prem3_summary=None,
            error_code=exc.code,
        )
    if isinstance(exc, InputContractMismatchError):
        return FitFailureClassification(
            failure_class=FitFailureClass.INPUT_CONTRACT_ERROR,
            failure_stage=FitFailureStage.MODEL_INITIALIZATION,
            status=FitRunStatus.FAILED_PRE_FIT,
            retry_semantics=RetrySemantics.NEW_FIT_PLAN_REQUIRED,
            sampling_started=False,
            next_actions=(FitNextActionType.REVIEW_MODEL_SPEC.value,),
            library=None,
            library_version=None,
            exception_type=exception_type,
            official_message=official,
            prem3_summary=None,
            error_code=exc.code,
        )
    if isinstance(exc, PriorValidationFailedError):
        return FitFailureClassification(
            failure_class=FitFailureClass.PRIOR_VALIDATION_ERROR,
            failure_stage=FitFailureStage.MODEL_INITIALIZATION,
            status=FitRunStatus.FAILED_PRE_FIT,
            retry_semantics=RetrySemantics.NEW_MODEL_DESIGN_REQUIRED,
            sampling_started=False,
            next_actions=(FitNextActionType.REVIEW_MODEL_SPEC.value,),
            library=OFFICIAL_MERIDIAN_LIBRARY,
            library_version=PINNED_RUNTIME_VERSION,
            exception_type=exception_type,
            official_message=official,
            prem3_summary=None,
            error_code=exc.code,
        )
    if isinstance(exc, SerdeError):
        return FitFailureClassification(
            failure_class=FitFailureClass.SERIALIZATION_ERROR,
            failure_stage=FitFailureStage.SERIALIZATION,
            status=FitRunStatus.FAILED_RUNTIME,
            retry_semantics=RetrySemantics.EXACT_RETRY_ALLOWED,
            sampling_started=True,
            next_actions=(),
            library=OFFICIAL_MERIDIAN_LIBRARY,
            library_version=PINNED_RUNTIME_VERSION,
            exception_type=exception_type,
            official_message=official,
            prem3_summary=None,
            error_code=exc.code,
        )
    if isinstance(exc, ResourceExhaustedError) or _is_resource_text(official):
        return FitFailureClassification(
            failure_class=FitFailureClass.RESOURCE_EXHAUSTED,
            failure_stage=FitFailureStage.POSTERIOR_SAMPLING,
            status=FitRunStatus.FAILED_RUNTIME,
            retry_semantics=RetrySemantics.EXACT_RETRY_ALLOWED,
            sampling_started=True,
            next_actions=(),
            library=OFFICIAL_MERIDIAN_LIBRARY,
            library_version=PINNED_RUNTIME_VERSION,
            exception_type=exception_type,
            official_message=official,
            prem3_summary=None,
            error_code="RESOURCE_EXHAUSTED",
        )
    if isinstance(exc, ModelReviewFailedError):
        return FitFailureClassification(
            failure_class=FitFailureClass.OFFICIAL_REVIEW_ERROR,
            failure_stage=FitFailureStage.OFFICIAL_REVIEW,
            status=FitRunStatus.FAILED_REVIEW,
            retry_semantics=RetrySemantics.NOT_RETRYABLE,
            sampling_started=True,
            next_actions=(FitNextActionType.REVIEW_MODEL_SPEC.value,),
            library=OFFICIAL_MERIDIAN_LIBRARY,
            library_version=PINNED_RUNTIME_VERSION,
            exception_type=exception_type,
            official_message=official,
            prem3_summary=None,
            error_code=exc.code,
        )
    if isinstance(exc, (GpuNotVisibleError, MeridianImportError, GcsPersistenceError)):
        return FitFailureClassification(
            failure_class=FitFailureClass.INFRASTRUCTURE_ERROR,
            failure_stage=FitFailureStage.DISPATCH,
            status=FitRunStatus.FAILED_RUNTIME,
            retry_semantics=RetrySemantics.EXACT_RETRY_ALLOWED,
            sampling_started=False,
            next_actions=(),
            library=OFFICIAL_MERIDIAN_LIBRARY,
            library_version=PINNED_RUNTIME_VERSION,
            exception_type=exception_type,
            official_message=official,
            prem3_summary=None,
            error_code=getattr(exc, "code", "INFRASTRUCTURE_ERROR"),
        )
    if isinstance(exc, LedgerPublicationError):
        return FitFailureClassification(
            failure_class=FitFailureClass.INFRASTRUCTURE_ERROR,
            failure_stage=FitFailureStage.OFFICIAL_REVIEW,
            status=FitRunStatus.FAILED_RUNTIME,
            retry_semantics=RetrySemantics.EXACT_RETRY_ALLOWED,
            sampling_started=True,
            next_actions=(),
            library=None,
            library_version=None,
            exception_type=exception_type,
            official_message=official,
            prem3_summary=None,
            error_code=exc.code,
        )
    return FitFailureClassification(
        failure_class=FitFailureClass.MERIDIAN_RUNTIME_ERROR,
        failure_stage=FitFailureStage.UNKNOWN,
        status=FitRunStatus.FAILED_RUNTIME,
        retry_semantics=RetrySemantics.NEW_FIT_PLAN_REQUIRED,
        sampling_started=False,
        next_actions=(),
        library=OFFICIAL_MERIDIAN_LIBRARY,
        library_version=PINNED_RUNTIME_VERSION,
        exception_type=exception_type,
        official_message=official,
        prem3_summary=None,
        error_code=getattr(exc, "code", FitFailureClass.MERIDIAN_RUNTIME_ERROR.value),
    )


def classify_failure(exc: BaseException) -> str:
    if isinstance(exc, ModelSpecIdentifiabilityError) or is_geo_invariant_identifiability_error(
        exc
    ):
        return FitFailureClass.MODEL_SPEC_IDENTIFIABILITY_ERROR.value
    if isinstance(exc, ModelingError) and getattr(exc, "code", None):
        return _LEGACY_CODES.get(exc.code, "FIT_RUNTIME_ERROR")
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
    if _is_resource_text(str(exc)):
        return "RESOURCE_EXHAUSTED"
    return "FIT_RUNTIME_ERROR"


def _is_resource_text(text: str) -> bool:
    lowered = text.lower()
    return "resource exhausted" in lowered or "out of memory" in lowered or "oom" in lowered


def offers_exact_retry(classification: FitFailureClassification) -> bool:
    return classification.retry_semantics is RetrySemantics.EXACT_RETRY_ALLOWED
