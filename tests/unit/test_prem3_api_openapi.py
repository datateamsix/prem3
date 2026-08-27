"""OpenAPI freeze and drift tests."""

from __future__ import annotations

from pathlib import Path

from app.service.app import create_app
from app.service.openapi_export import (
    DEFAULT_OPENAPI_PATH,
    check_openapi,
    render_openapi_yaml,
    sha256_bytes,
)


def test_openapi_export_is_deterministic() -> None:
    first = render_openapi_yaml()
    second = render_openapi_yaml()
    assert first == second
    assert sha256_bytes(first) == sha256_bytes(second)


def test_committed_openapi_matches_application() -> None:
    errors = check_openapi(DEFAULT_OPENAPI_PATH)
    assert errors == []


def test_openapi_drift_is_detected(tmp_path: Path) -> None:
    tampered = tmp_path / "openapi.yaml"
    tampered.write_text("openapi: 3.1.0\ninfo:\n  title: tampered\n", encoding="utf-8")
    errors = check_openapi(tampered)
    assert errors


def test_operation_ids_are_unique() -> None:
    schema = create_app().openapi()
    ids: list[str] = []
    for operations in schema["paths"].values():
        for operation in operations.values():
            if isinstance(operation, dict) and "operationId" in operation:
                ids.append(operation["operationId"])
    assert ids
    assert len(ids) == len(set(ids))


def test_protected_routes_have_security_contract() -> None:
    schema = create_app().openapi()
    me = schema["paths"]["/v1/me"]["get"]
    assert me.get("security") == [{"HTTPBearer": []}]
    checkout = schema["paths"]["/v1/billing/checkout-session"]["post"]
    assert checkout.get("security") == [{"HTTPBearer": []}]


def test_openapi_contains_problem_detail() -> None:
    schema = create_app().openapi()
    assert "ProblemDetail" in schema["components"]["schemas"]


def test_openapi_contains_billing_session_contract() -> None:
    schema = create_app().openapi()
    names = " ".join(schema["components"]["schemas"])
    assert "BillingSessionResponse" in names
    assert "CheckoutSessionRequest" in names


def test_openapi_has_no_tenant_authority_input() -> None:
    schema = create_app().openapi()
    # Presentation may mention tenant_id on MeResponse, but not as an input parameter.
    for _path, operations in schema["paths"].items():
        for operation in operations.values():
            if not isinstance(operation, dict):
                continue
            for parameter in operation.get("parameters") or []:
                name = str(parameter.get("name", "")).lower()
                assert name not in {
                    "tenant_id",
                    "organization_id",
                    "x-tenant-id",
                    "stripe_price_id",
                    "customer_id",
                }
            body = operation.get("requestBody") or {}
            content = str(body).lower()
            assert "tenant_id" not in content
            assert "stripe_price_id" not in content
            assert "x-tenant-id" not in content


def test_openapi_has_no_stripe_price_id_input() -> None:
    schema = create_app().openapi()
    assert "stripe_price_id" not in str(schema["paths"]).lower()


def test_openapi_has_no_firestore_document_shapes() -> None:
    schema = create_app().openapi()
    blob = str(schema).lower()
    assert "identity_org_mappings" not in blob
    assert "processed_webhook_events" not in blob
    assert "investment_planning_index" not in blob
