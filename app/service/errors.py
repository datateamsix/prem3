"""Typed ProblemDetail errors for prem3-api."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ProblemFieldError(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    field: str
    message: str


class ProblemDetail(BaseModel):
    """application/problem+json. Frontend must use ``code``, never parse detail."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: str
    title: str
    status: int
    detail: str
    code: str
    request_id: str
    instance: str | None = None
    errors: list[ProblemFieldError] | None = None


PROBLEM_TYPE_BASE = "https://prem3.dev/problems"


class APIError(Exception):
    def __init__(
        self,
        *,
        code: str,
        status: int,
        title: str,
        detail: str,
        errors: list[ProblemFieldError] | None = None,
    ) -> None:
        super().__init__(detail)
        self.code = code
        self.status = status
        self.title = title
        self.detail = detail
        self.errors = errors

    def to_problem(self, *, request_id: str, instance: str | None = None) -> ProblemDetail:
        return ProblemDetail(
            type=f"{PROBLEM_TYPE_BASE}/{self.code.lower()}",
            title=self.title,
            status=self.status,
            detail=self.detail,
            code=self.code,
            request_id=request_id,
            instance=instance,
            errors=self.errors,
        )


def auth_required() -> APIError:
    return APIError(
        code="AUTH_REQUIRED",
        status=401,
        title="Authentication required",
        detail="A verified identity is required for this operation.",
    )


def auth_provider_not_configured() -> APIError:
    return APIError(
        code="AUTH_PROVIDER_NOT_CONFIGURED",
        status=503,
        title="Identity provider not configured",
        detail="The identity verifier is not configured.",
    )


def auth_provider_unavailable() -> APIError:
    return APIError(
        code="AUTH_PROVIDER_UNAVAILABLE",
        status=503,
        title="Identity provider unavailable",
        detail="The identity provider could not be reached.",
    )


def organization_context_required() -> APIError:
    return APIError(
        code="ORGANIZATION_CONTEXT_REQUIRED",
        status=403,
        title="Organization context required",
        detail="An active organization is required for tenant access.",
    )


def tenant_not_found() -> APIError:
    return APIError(
        code="TENANT_NOT_FOUND",
        status=404,
        title="Tenant not found",
        detail="No PreM3 tenant is mapped for the verified organization.",
    )


def resource_not_found() -> APIError:
    return APIError(
        code="RESOURCE_NOT_FOUND",
        status=404,
        title="Resource not found",
        detail="The requested resource was not found.",
    )


def entitlement_unavailable() -> APIError:
    return APIError(
        code="ENTITLEMENT_UNAVAILABLE",
        status=403,
        title="Entitlement unavailable",
        detail="No usable entitlement snapshot is available for this tenant.",
    )


def entitlement_denied() -> APIError:
    return APIError(
        code="ENTITLEMENT_DENIED",
        status=403,
        title="Entitlement denied",
        detail="The current entitlement does not allow this operation.",
    )


def project_limit_reached() -> APIError:
    return APIError(
        code="PROJECT_LIMIT_REACHED",
        status=409,
        title="Project limit reached",
        detail="Active MMM Project capacity has been reached.",
    )


def billing_provider_not_configured() -> APIError:
    return APIError(
        code="BILLING_PROVIDER_NOT_CONFIGURED",
        status=503,
        title="Billing provider not configured",
        detail="The billing gateway is not configured.",
    )


def billing_provider_unavailable() -> APIError:
    return APIError(
        code="BILLING_PROVIDER_UNAVAILABLE",
        status=503,
        title="Billing provider unavailable",
        detail="The billing provider could not be reached.",
    )


def billing_configuration_error() -> APIError:
    return APIError(
        code="BILLING_CONFIGURATION_ERROR",
        status=503,
        title="Billing configuration error",
        detail="Paid billing is not configured for this plan.",
    )


def billing_customer_unavailable() -> APIError:
    return APIError(
        code="BILLING_CUSTOMER_UNAVAILABLE",
        status=409,
        title="Billing customer unavailable",
        detail="No billing customer is mapped for this tenant.",
    )


def governance_denied(*, code: str, detail: str) -> APIError:
    return APIError(
        code=code,
        status=409,
        title="Governance denied",
        detail=detail,
    )


def validation_error(errors: list[ProblemFieldError]) -> APIError:
    return APIError(
        code="VALIDATION_ERROR",
        status=422,
        title="Validation error",
        detail="The request failed validation.",
        errors=errors,
    )


def evaluation_dispatch_unavailable() -> APIError:
    return APIError(
        code="EVALUATION_DISPATCH_UNAVAILABLE",
        status=503,
        title="Evaluation dispatch unavailable",
        detail="The Evaluation was accepted but durable dispatch could not be queued.",
    )


def service_identity_required() -> APIError:
    return APIError(
        code="SERVICE_IDENTITY_REQUIRED",
        status=401,
        title="Service identity required",
        detail="A verified service identity is required for this operation.",
    )


def internal_error() -> APIError:
    return APIError(
        code="INTERNAL_ERROR",
        status=500,
        title="Internal error",
        detail="An unexpected error occurred.",
    )


def problem_json(problem: ProblemDetail) -> dict[str, Any]:
    return problem.model_dump(mode="json", exclude_none=True)
