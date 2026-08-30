"""Fail-closed Planning errors. Codes are machine-stable."""

from __future__ import annotations


class PlanningError(Exception):
    code = "PLANNING_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class PlanningAuthorityError(PlanningError):
    code = "PLANNING_AUTHORITY_DENIED"


class PersistenceBarrierError(PlanningError):
    code = "PLANNING_PERSISTENCE_BARRIER"


class UnresolvedMarketIdentityError(PlanningError):
    code = "UNRESOLVED_MARKET_IDENTITY"


class CanonicalMarketContractPendingError(PlanningError):
    code = "CANONICAL_MARKET_CONTRACT_PENDING"


class UnresolvedChannelIdentityError(PlanningError):
    code = "UNRESOLVED_CHANNEL_IDENTITY"


class PlanningValueAuthorityError(PlanningError):
    code = "LEGACY_ALLOCATION_NOT_VALUE_AUTHORITY"


class PortfolioAssemblyNotImplementedError(PlanningError):
    code = "PORTFOLIO_ASSEMBLY_NOT_IMPLEMENTED"


class SourceChangedSinceLoadError(PlanningError):
    code = "SOURCE_CHANGED_SINCE_LOAD"


class SourceUnidentifiableError(PlanningError):
    code = "SOURCE_VERSION_UNVERIFIABLE"


class BudgetFormatError(PlanningError):
    code = "FORMAT_UNSUPPORTED"


class BudgetFolderDegradedError(PlanningError):
    code = "BUDGET_FOLDER_DEGRADED"


class MixedGrainUnresolvedError(PlanningError):
    code = "MIXED_GRAIN_UNRESOLVED"


class ActualsSourceNotConfiguredError(PlanningError):
    code = "ACTUALS_SOURCE_NOT_CONFIGURED"


class ActualsSourceUnavailableError(PlanningError):
    code = "ACTUALS_SOURCE_UNAVAILABLE"


class ActualsSchemaInvalidError(PlanningError):
    code = "ACTUALS_SCHEMA_INVALID"


class PeriodMappingRequiredError(PlanningError):
    code = "PERIOD_MAPPING_REQUIRED"


class CurrencyReviewRequiredError(PlanningError):
    code = "CURRENCY_REVIEW_REQUIRED"


class SourceAuthorityInvalidError(PlanningError):
    code = "SOURCE_AUTHORITY_INVALID"


class ProductionActualsSourceNotReadyError(PlanningError):
    code = "PRODUCTION_ACTUALS_SOURCE_NOT_READY"


class BqAuthorizationFailedError(PlanningError):
    code = "BQ_AUTHORIZATION_FAILED"


class BqSourceNotFoundError(PlanningError):
    code = "BQ_SOURCE_NOT_FOUND"


class BqLocationMismatchError(PlanningError):
    code = "BQ_LOCATION_MISMATCH"


class BqQueryFailedError(PlanningError):
    code = "BQ_QUERY_FAILED"


class ActualsMarketMappingRequiredError(PlanningError):
    code = "ACTUALS_MARKET_MAPPING_REQUIRED"


class ActualsChannelMappingRequiredError(PlanningError):
    code = "ACTUALS_CHANNEL_MAPPING_REQUIRED"


class ActualsDuplicateGrainError(PlanningError):
    code = "ACTUALS_DUPLICATE_GRAIN"


class ExposureSourceNotReadyError(PlanningError):
    code = "EXPOSURE_SOURCE_NOT_READY"


class ExposureMetricNotComparableError(PlanningError):
    code = "EXPOSURE_METRIC_NOT_COMPARABLE"


class ExposureDataStaleError(PlanningError):
    code = "EXPOSURE_DATA_STALE"


class ExposureCoverageInsufficientError(PlanningError):
    code = "EXPOSURE_COVERAGE_INSUFFICIENT"


class ExposureEntityMappingRequiredError(PlanningError):
    code = "EXPOSURE_ENTITY_MAPPING_REQUIRED"


class ExposureModelInputUnsupportedError(PlanningError):
    code = "EXPOSURE_MODEL_INPUT_UNSUPPORTED"


class ExposureHardConstraintUnsupportedError(PlanningError):
    code = "EXPOSURE_HARD_CONSTRAINT_UNSUPPORTED"


class SpendQualityRelationshipRequiredError(PlanningError):
    code = "SPEND_QUALITY_RELATIONSHIP_REQUIRED"


class ExposureGuardrailReviewRequiredError(PlanningError):
    code = "EXPOSURE_GUARDRAIL_REVIEW_REQUIRED"
