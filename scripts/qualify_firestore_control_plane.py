#!/usr/bin/env python3
"""Optional live Firestore control-plane qualification.

NEVER invoked by pytest/CI. Explicit operator command only.

Usage:
  py -3.13 scripts/qualify_firestore_control_plane.py --execute

Safety:
  - requires GOOGLE_CLOUD_PROJECT=modelready-m3
  - requires FIRESTORE_DATABASE=(default) (or unset → default)
  - uses a unique synthetic namespace/prefix
  - deletes all synthetic documents before exit
  - never touches GCS, BigQuery, Clerk, or Stripe APIs
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import UTC, datetime, timedelta

from google.auth import default as google_auth_default
from google.auth import impersonated_credentials

from app.config import load_settings
from app.control_plane.entitlements import PlanId, entitlement_for_plan
from app.control_plane.firestore_repo import (
    COLLECTION_IDENTITY_MAPPINGS,
    COLLECTION_WEBHOOKS,
    FirestoreControlPlaneRepository,
    build_firestore_client,
)
from app.control_plane.layout import identity_mapping_doc_id, webhook_event_doc_id
from app.control_plane.models import (
    EntitlementSource,
    IdentityProvider,
    IdentityProviderOrganizationMapping,
    WebhookClaimStatus,
    WebhookProvider,
)
from app.core.errors import ProjectLimitReachedError

EXPECTED_PROJECT = "modelready-m3"
EXPECTED_DATABASE = "(default)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Required. Without this flag the script refuses to run.",
    )
    parser.add_argument(
        "--impersonate-service-account",
        default=None,
        help="Optional. Impersonate this service account instead of using raw ADC.",
    )
    args = parser.parse_args(argv)
    if not args.execute:
        print("LIVE_FIRESTORE_QUALIFICATION_NOT_RUN")
        print("Pass --execute to run against the empty (default) database.")
        return 2

    settings = load_settings()
    if settings.project_id != EXPECTED_PROJECT:
        print("LIVE_FIRESTORE_QUALIFICATION_NOT_RUN")
        print(f"Unexpected project_id={settings.project_id!r}; expected {EXPECTED_PROJECT!r}.")
        return 3
    if settings.firestore_database != EXPECTED_DATABASE:
        print("LIVE_FIRESTORE_QUALIFICATION_NOT_RUN")
        print(
            f"Unexpected FIRESTORE_DATABASE={settings.firestore_database!r}; "
            f"expected {EXPECTED_DATABASE!r}."
        )
        return 3

    namespace = f"qual_{uuid.uuid4().hex[:12]}"
    print(f"namespace={namespace}")
    try:
        if args.impersonate_service_account:
            source, _ = google_auth_default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            creds = impersonated_credentials.Credentials(
                source_credentials=source,
                target_principal=args.impersonate_service_account,
                target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            client = build_firestore_client(
                project_id=settings.project_id,
                database=settings.firestore_database,
                credentials=creds,
            )
            repo = FirestoreControlPlaneRepository(client)
            print(f"identity={args.impersonate_service_account}")
        else:
            repo = FirestoreControlPlaneRepository.from_settings(
                project_id=settings.project_id,
                database=settings.firestore_database,
            )
            print("identity=application_default_credentials")
    except Exception as exc:  # noqa: BLE001 — report unavailable ADC/API clearly
        print("LIVE_FIRESTORE_QUALIFICATION_NOT_RUN")
        print(f"Firestore client unavailable: {exc}")
        return 4

    tenant_id: str | None = None
    identity_key: str | None = None
    webhook_key: str | None = None
    try:
        now = datetime.now(UTC)
        provider_org = f"org_{namespace}"
        mapping = IdentityProviderOrganizationMapping(
            provider=IdentityProvider.CLERK,
            provider_organization_id=provider_org,
            tenant_id="placeholder",
            created_at=now,
            updated_at=now,
        )
        tenant = repo.create_tenant(
            display_name=f"Qualification {namespace}",
            identity_mapping=mapping,
        )
        tenant_id = tenant.tenant_id
        identity_key = identity_mapping_doc_id("clerk", provider_org)

        resolved = repo.get_tenant_id_for_provider_org(
            provider="clerk", provider_organization_id=provider_org
        )
        assert resolved == tenant.tenant_id
        entitlement = repo.get_current_entitlement(tenant.tenant_id)
        assert entitlement.plan_id == PlanId.PLANNER
        assert entitlement.max_active_projects == 0

        try:
            repo.create_workspace_with_capacity(tenant_id=tenant.tenant_id, name="blocked")
            raise AssertionError("Planner capacity should block workspace create")
        except ProjectLimitReachedError:
            pass

        repo.put_entitlement_snapshot(
            entitlement_for_plan(
                tenant_id=tenant.tenant_id,
                plan_id=PlanId.PROJECT,
                source=EntitlementSource.MANUAL_GRANT,
            )
        )
        workspace = repo.create_workspace_with_capacity(
            tenant_id=tenant.tenant_id, name=f"ws-{namespace}"
        )
        try:
            repo.create_workspace_with_capacity(
                tenant_id=tenant.tenant_id, name=f"ws2-{namespace}"
            )
            raise AssertionError("Project plan must allow only one active project")
        except ProjectLimitReachedError:
            pass

        dataset = repo.create_dataset(
            tenant_id=tenant.tenant_id,
            workspace_id=workspace.workspace_id,
            name=f"ds-{namespace}",
        )
        assert (
            repo.get_dataset_for_workspace(
                tenant_id=tenant.tenant_id,
                workspace_id=workspace.workspace_id,
                dataset_id=dataset.dataset_id,
            )
            is not None
        )

        event_id = f"evt_{namespace}"
        webhook_key = webhook_event_doc_id("stripe", event_id)
        claimed_at = datetime.now(UTC)
        claim1 = repo.claim_webhook_event(
            provider=WebhookProvider.STRIPE,
            provider_event_id=event_id,
            event_type="qualification.test",
            lease_seconds=60,
            now=claimed_at,
        )
        claim2 = repo.claim_webhook_event(
            provider=WebhookProvider.STRIPE,
            provider_event_id=event_id,
            event_type="qualification.test",
            lease_seconds=60,
            now=claimed_at + timedelta(seconds=1),
        )
        stale = repo.claim_webhook_event(
            provider=WebhookProvider.STRIPE,
            provider_event_id=event_id,
            event_type="qualification.test",
            lease_seconds=60,
            now=claimed_at + timedelta(seconds=61),
        )
        assert claim1.status == WebhookClaimStatus.WON
        assert claim2.status == WebhookClaimStatus.ALREADY_CLAIMED
        assert stale.status == WebhookClaimStatus.WON
        repo.mark_webhook_event_processed(
            provider=WebhookProvider.STRIPE,
            provider_event_id=event_id,
            result="qualification-ok",
        )

        print("transaction_results=tenant,identity,planner_block,capacity,dataset,webhook OK")
    except Exception as exc:  # noqa: BLE001
        print("LIVE_FIRESTORE_QUALIFICATION_NOT_RUN")
        print(f"Qualification failed: {exc}")
        _cleanup(repo, tenant_id, identity_key, webhook_key)
        return 5

    cleanup_ok = _cleanup(repo, tenant_id, identity_key, webhook_key)
    if not cleanup_ok:
        print("LIVE_FIRESTORE_QUALIFICATION_NOT_RUN")
        print("Cleanup verification failed; inspect Firestore for leftover qual_* docs.")
        return 6

    print("LIVE_FIRESTORE_CONTROL_PLANE_PROOF")
    print(f"project={settings.project_id}")
    print(f"database={settings.firestore_database}")
    print(f"collection_namespace={namespace}")
    print(f"tenant_id={tenant_id}")
    print("cleanup=verified")
    print(
        "note=Firestore-adapter qualification only; not prem3-api/Clerk/Stripe/E2E SaaS proof."
    )
    return 0


def _cleanup(
    repo: FirestoreControlPlaneRepository,
    tenant_id: str | None,
    identity_key: str | None,
    webhook_key: str | None,
) -> bool:
    try:
        if tenant_id is not None:
            repo.delete_document_tree_for_qualification(tenant_id)
            if repo.get_tenant(tenant_id) is not None:
                return False
        if identity_key is not None:
            repo._db.collection(COLLECTION_IDENTITY_MAPPINGS).document(identity_key).delete()
        if webhook_key is not None:
            repo._db.collection(COLLECTION_WEBHOOKS).document(webhook_key).delete()
            if (
                repo.get_webhook_event(
                    provider=WebhookProvider.STRIPE,
                    provider_event_id=webhook_key.split("__", 1)[-1],
                )
                is not None
            ):
                return False
        return True
    except Exception:  # noqa: BLE001
        return False


if __name__ == "__main__":
    sys.exit(main())
