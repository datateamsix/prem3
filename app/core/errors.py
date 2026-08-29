"""ModelReady domain exceptions."""


class ModelReadyError(Exception):
    """Base exception for ModelReady failures."""


class ValidationBlockedError(ModelReadyError):
    """Raised when deterministic validation prevents MODEL_READY."""


class AssignmentInitError(ValidationBlockedError):
    """Typed assignment initialization failure. Reason codes are machine-stable."""

    def __init__(
        self,
        message: str,
        *,
        reason: str,
        source: str | None = None,
        authority: str = "PREM3_DETERMINISTIC",
        recoverability: str = "USER_REQUIRED",
        owner: str = "user",
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.source = source
        self.authority = authority
        self.recoverability = recoverability
        self.owner = owner


class ApprovalRequiredError(ModelReadyError):
    """Raised when a transformation requires an explicit human decision."""


class PublishParityError(ModelReadyError):
    """Raised when BigQuery output does not match the validated artifact."""


class RegistryTrustError(ModelReadyError):
    """Raised when a directory registry card is used as an executable field map."""


class SafetyViolationError(ModelReadyError):
    """Raised when a requested transform violates a deterministic safety rule."""


class IllegalTransitionError(ModelReadyError):
    """Raised when a run attempts an illegal state-machine transition."""


class TenantContextMissingError(ModelReadyError):
    """Raised when a tenant-scoped operation has no bound TenantContext."""


class WorkspaceContextMissingError(ModelReadyError):
    """Raised when a project-scoped operation has no bound WorkspaceContext."""


class InvalidResourceIdentifierError(ModelReadyError):
    """Raised when a path/storage identifier is empty, traversal-shaped, or unsafe."""


class ExecutionContextMissingError(ModelReadyError):
    """Raised when Dataset execution has no bound ExecutionContext."""


class AuthorityMismatchError(ModelReadyError):
    """Raised when execution identity contradicts bound tenant/workspace authority."""


class ControlPlaneError(ModelReadyError):
    """Base exception for Mission 2 operational control-plane failures."""


class TenantNotFoundError(ControlPlaneError):
    """Raised when a tenant document cannot be resolved under current authority."""


class WorkspaceNotFoundError(ControlPlaneError):
    """Raised when an MMM Project cannot be resolved under tenant authority."""


class DatasetNotFoundError(ControlPlaneError):
    """Raised when a Dataset cannot be resolved under tenant/workspace authority."""


class ProjectLimitReachedError(ControlPlaneError):
    """Raised when active MMM Project capacity would be exceeded."""


class EntitlementUnavailableError(ControlPlaneError):
    """Raised when no usable entitlement snapshot exists for a tenant."""


class ProviderMappingConflictError(ControlPlaneError):
    """Raised when a provider organization is already mapped to another tenant."""


class WebhookAlreadyProcessedError(ControlPlaneError):
    """Raised when a provider webhook event was already claimed or processed."""


class DatasetReparentDeniedError(ControlPlaneError):
    """Raised when a Dataset would be moved across workspace or tenant authority."""


class MeasurementHomeConflictError(ControlPlaneError):
    """Raised when a conflicted prem3_modeling binding is used as resource authority."""


class TrackConfigurationImmutableError(ControlPlaneError):
    """Raised when a consumed MeasurementTrack configuration would be rewritten."""
