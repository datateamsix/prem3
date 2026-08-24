"""Server-owned PreM3 resource identifier generation.

Provider IDs (Clerk, Stripe) must never be embedded. Generated values satisfy
``validate_resource_identifier`` so they may later appear in GCS path segments.
"""

from __future__ import annotations

from uuid import uuid4

from app.core.identifiers import validate_resource_identifier


def _opaque(prefix: str) -> str:
    # Prefix + 20 hex chars stays well under the 128-char identifier limit.
    value = f"{prefix}_{uuid4().hex[:20]}"
    return validate_resource_identifier(value, field="resource_id")


def new_tenant_id() -> str:
    return _opaque("ten")


def new_workspace_id() -> str:
    return _opaque("wsp")


def new_dataset_id() -> str:
    return _opaque("dset")


def new_entitlement_snapshot_id() -> str:
    return _opaque("ent")


def new_upload_id() -> str:
    return _opaque("upl")


def new_upload_file_id() -> str:
    return _opaque("ufile")


def new_run_id() -> str:
    return _opaque("run")


def new_dispatch_id() -> str:
    return _opaque("dsp")


def new_google_connection_id() -> str:
    return _opaque("gconn")


def new_oauth_transaction_id() -> str:
    return _opaque("goauth")


def new_credential_ref() -> str:
    return _opaque("gcred")


def new_receipt_id() -> str:
    return _opaque("rcpt")


def new_import_object_id() -> str:
    return _opaque("iobj")


def new_materialization_id() -> str:
    return _opaque("matl")


def new_publish_id() -> str:
    return _opaque("pub")


def new_track_id() -> str:
    return _opaque("trk")


def new_model_version_id() -> str:
    return _opaque("mver")


def new_model_plan_id() -> str:
    return _opaque("mplan")


def new_decision_id() -> str:
    return _opaque("mdec")


def new_fit_run_id() -> str:
    return _opaque("mfit")


def new_approval_id() -> str:
    return _opaque("mapv")


def new_fit_dispatch_id() -> str:
    return _opaque("mdsp")
