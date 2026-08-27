"""Firestore collection layout for the Mission 2 operational control plane.

Authority-qualified paths. PreM3 IDs are document IDs. Provider IDs are mapped
attributes or encoded into *mapping* document IDs only — never tenant/workspace/
dataset authority.

Layout
------
tenants/{tenant_id}
  fields: tenant_id, display_name, status, created_at, updated_at,
          current_entitlement_snapshot_id, active_workspace_count

identity_org_mappings/{provider}__{provider_organization_id}
  global lookup: provider org → PreM3 tenant_id
  one authoritative mapping per provider organization

tenants/{tenant_id}/memberships/{provider}__{provider_user_id}

tenants/{tenant_id}/workspaces/{workspace_id}

tenants/{tenant_id}/workspaces/{workspace_id}/datasets/{dataset_id}

tenants/{tenant_id}/entitlements/{snapshot_id}
  immutable snapshots; current pointer lives on the tenant document

tenants/{tenant_id}/billing_customers/{billing_provider}

tenants/{tenant_id}/billing_subscriptions/{billing_provider}

tenants/{tenant_id}/evaluation_refs/{run_id}
  Evaluation resource (tenant-scoped run_id lookup). Dual-written with dataset path.

tenants/{tenant_id}/workspaces/{workspace_id}/datasets/{dataset_id}/uploads/{upload_id}

tenants/{tenant_id}/workspaces/{workspace_id}/datasets/{dataset_id}/evaluations/{run_id}
  Dataset-scoped Evaluation list authority. Same payload as evaluation_refs.

google_oauth_transactions/{state_hash}
  Short-lived OAuth CSRF state. Tenant is inside the document; callback never
  accepts tenant/workspace/dataset from Google query parameters.

tenants/{tenant_id}/google_connections/{connection_id}

tenants/{tenant_id}/credential_envelopes/{credential_ref}
  Ciphertext only. Never a plaintext Google refresh token.

tenants/{tenant_id}/workspaces/{workspace_id}/drive_bindings/current

tenants/{tenant_id}/workspaces/{workspace_id}/bigquery_bindings/current

tenants/{tenant_id}/workspaces/{workspace_id}/datasets/{dataset_id}/import_selections/current

tenants/{tenant_id}/workspaces/{workspace_id}/datasets/{dataset_id}/import_receipts/{receipt_id}
  plus import_receipts/current pointer. Historical receipts are retained.

tenants/{tenant_id}/workspaces/{workspace_id}/identity_graph/...
  Marketing Identity Graph metadata (campaigns, markets, tracking, receipts).
  Not people, budget, events, or performance.

processed_webhook_events/{provider}__{provider_event_id}

Tenant deletion (future)
------------------------
Delete the tenant document and all subcollections under tenants/{tenant_id},
plus identity_org_mappings rows that point at the tenant, plus any
processed_webhook_events if retained as tenant-scoped (currently global by
provider event id).

External remnants (not Firestore):
- GCS tenant prefixes
- BigQuery model-consumption dataset / shared ledger rows
- globally promoted de-identified registry knowledge
"""

from __future__ import annotations

from app.control_plane.models import BillingProvider, IdentityProvider, WebhookProvider


def identity_mapping_doc_id(provider: IdentityProvider | str, provider_organization_id: str) -> str:
    return f"{_provider_token(provider)}__{_safe_segment(provider_organization_id)}"


def membership_doc_id(provider: IdentityProvider | str, provider_user_id: str) -> str:
    return f"{_provider_token(provider)}__{_safe_segment(provider_user_id)}"


def webhook_event_doc_id(provider: WebhookProvider | str, provider_event_id: str) -> str:
    return f"{_provider_token(provider)}__{_safe_segment(provider_event_id)}"


def billing_customer_doc_id(billing_provider: BillingProvider | str) -> str:
    return _provider_token(billing_provider)


def billing_subscription_doc_id(billing_provider: BillingProvider | str) -> str:
    return _provider_token(billing_provider)


def _provider_token(provider: object) -> str:
    value = provider.value if hasattr(provider, "value") else str(provider)
    return _safe_segment(value.lower())


def _safe_segment(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("document key segment must not be empty")
    # Provider IDs may contain characters unsafe as bare Firestore IDs; encode.
    return (
        text.replace("/", "_")
        .replace("\\", "_")
        .replace(" ", "_")
        .replace(".", "_")
    )
