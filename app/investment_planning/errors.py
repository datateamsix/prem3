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
