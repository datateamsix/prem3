"""Typed modeling failures. Customer APIs must not leak stack traces."""

from __future__ import annotations

from app.core.errors import ModelReadyError


class ModelingError(ModelReadyError):
    """Base modeling-domain failure."""

    code = "MODELING_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class InputContractMismatchError(ModelingError):
    code = "INPUT_CONTRACT_MISMATCH"


class MeridianCompatibilityError(ModelingError):
    code = "MERIDIAN_COMPATIBILITY_ERROR"


class ModelSpecInvalidError(ModelingError):
    code = "MODEL_SPEC_INVALID"


class ModelSpecIdentifiabilityError(ModelingError):
    code = "MODEL_SPEC_IDENTIFIABILITY_ERROR"

    def __init__(
        self,
        message: str,
        *,
        official_message: str | None = None,
        exception_type: str = "ValueError",
        code: str | None = None,
    ) -> None:
        super().__init__(message, code=code)
        self.official_message = official_message or message
        self.exception_type = exception_type


class ExactRetryNotAllowedError(ModelingError):
    code = "EXACT_RETRY_NOT_ALLOWED"


class PriorValidationFailedError(ModelingError):
    code = "PRIOR_VALIDATION_FAILED"


class ResourceExhaustedError(ModelingError):
    code = "RESOURCE_EXHAUSTED"


class FitRuntimeError(ModelingError):
    code = "FIT_RUNTIME_ERROR"


class SerdeError(ModelingError):
    code = "SERDE_ERROR"


class ModelReviewFailedError(ModelingError):
    code = "MODEL_REVIEW_FAILED"


class ArtifactVerificationFailedError(ModelingError):
    code = "ARTIFACT_VERIFICATION_FAILED"


class FitApprovalRequiredError(ModelingError):
    code = "FIT_APPROVAL_REQUIRED"


class StaleApprovalError(ModelingError):
    code = "STALE_APPROVAL"


class ModelVersionImmutableError(ModelingError):
    code = "MODEL_VERSION_IMMUTABLE"


class IllegalModelingTransitionError(ModelingError):
    code = "ILLEGAL_MODELING_TRANSITION"


class ExternalAssetDisabledError(ModelingError):
    code = "EXTERNAL_ASSET_DISABLED"


class DecisionNotFoundError(ModelingError):
    code = "RESOURCE_NOT_FOUND"


class ModelVersionNotFoundError(ModelingError):
    code = "RESOURCE_NOT_FOUND"


class LedgerPublicationError(ModelingError):
    code = "LEDGER_PUBLICATION_FAILED"


class FakeRuntimeAcceptanceError(ModelingError):
    code = "FAKE_RUNTIME_INELIGIBLE"


class QualificationAcceptanceError(ModelingError):
    code = "QUALIFICATION_INELIGIBLE"


class HumanApprovalRequiredError(ModelingError):
    code = "HUMAN_APPROVAL_REQUIRED"


class GcsPersistenceError(ModelingError):
    code = "GCS_PERSISTENCE_FAILED"


class FirestorePersistenceError(ModelingError):
    code = "FIRESTORE_PERSISTENCE_FAILED"


class MeridianImportError(ModelingError):
    code = "MERIDIAN_IMPORT_FAILED"


class GpuNotVisibleError(ModelingError):
    code = "GPU_NOT_VISIBLE"


class WorkerProvenanceError(ModelingError):
    code = "WORKER_PROVENANCE_INVALID"
