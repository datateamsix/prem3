from __future__ import annotations

import pytest

from app.identity_graph.enums import (
    AudienceRefreshCadence,
    AudienceSourceKind,
    AudienceType,
    IdentitySourceAuthority,
)
from app.identity_graph.errors import IdentityGraphError
from tests.unit.identity_graph.conftest import PROJECT_ID, TENANT_ID


def test_audience_type_and_source_kind_are_required(graph) -> None:
    audience = graph.create_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="Typed",
        actor_id="user-a",
        audience_type=AudienceType.INTENT,
        source_kind=AudienceSourceKind.USER_DECLARED,
        refresh_cadence=AudienceRefreshCadence.WEEKLY,
        effective_start_date="2026-01-01",
        effective_end_date="2026-12-31",
    )
    assert audience.audience_type == AudienceType.INTENT
    assert audience.source_kind == AudienceSourceKind.USER_DECLARED
    assert audience.source_authority == IdentitySourceAuthority.USER_DECLARED
    assert audience.refresh_cadence == AudienceRefreshCadence.WEEKLY


def test_business_iq_source_kind_sets_source_authority(graph) -> None:
    audience = graph.create_audience(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        name="BIQ defined",
        actor_id="user-a",
        audience_type=AudienceType.LIFECYCLE,
        source_kind=AudienceSourceKind.BUSINESS_IQ_DEFINED,
        source_ref="biq:segment:core-buyers",
    )
    assert audience.source_authority == IdentitySourceAuthority.BUSINESS_IQ_DEFINED


def test_source_ref_rejects_sql_and_person_markers(graph) -> None:
    with pytest.raises(IdentityGraphError) as exc:
        graph.create_audience(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            name="SQL",
            actor_id="user-a",
            audience_type=AudienceType.CRM_SEGMENT,
            source_kind=AudienceSourceKind.BIGQUERY_DEFINED,
            source_ref="SELECT syn_id FROM crm_table WHERE syn_id IS NOT NULL",
        )
    assert exc.value.code == "SOURCE_REF_FORBIDDEN"
    with pytest.raises(IdentityGraphError) as second:
        graph.create_audience(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            name="At sign",
            actor_id="user-a",
            audience_type=AudienceType.CRM_SEGMENT,
            source_kind=AudienceSourceKind.CRM_DEFINED,
            source_ref="syn_contact_id@example.invalid",
        )
    assert second.value.code == "SOURCE_REF_FORBIDDEN"


def test_effective_date_order_is_validated(graph) -> None:
    with pytest.raises(IdentityGraphError) as exc:
        graph.create_audience(
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            name="Dates",
            actor_id="user-a",
            audience_type=AudienceType.CUSTOM,
            source_kind=AudienceSourceKind.USER_DECLARED,
            effective_start_date="2026-06-01",
            effective_end_date="2026-01-01",
        )
    assert exc.value.code == "DATE_ORDER"
