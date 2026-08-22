import pytest

from app.data_foundation.contracts import ResourceIdentity, SourceCandidate, SourceContract
from app.data_foundation.drive.files import fingerprint_bytes, register_file
from app.data_foundation.drive.grouping import group_file_series
from app.data_foundation.drive.ingestion import parse_drive_payload
from app.data_foundation.drive.naming import canonical_logical_name, provider_slug
from app.data_foundation.enums import CandidateGroup, LocationType, ProvenanceClass


def test_root_enforcement(df_context) -> None:
    with pytest.raises(PermissionError, match="outside the bound root"):
        register_file(
            context=df_context,
            drive_file_id="file1",
            original_name="meta.csv",
            parent_folder_id="some_other_folder",
            payload=b"date,spend\n2026-01-01,1\n",
            mime_type="text/csv",
            source_slug="meta_ads",
        )


def test_same_fingerprint_identity_and_rename_is_non_destructive(df_context) -> None:
    payload = b"date,spend\n2026-01-01,1\n"
    first = register_file(
        context=df_context,
        drive_file_id="file1",
        original_name="ugly name.csv",
        parent_folder_id="root_prem3",
        payload=payload,
        mime_type="text/csv",
        source_slug="meta_ads",
        start_date="2026-01-01",
        end_date="2026-01-31",
    )
    second = register_file(
        context=df_context,
        drive_file_id="file2",
        original_name="ugly name.csv",
        parent_folder_id="root_prem3",
        payload=b"date,spend\n2026-02-01,2\n",
        mime_type="text/csv",
        source_slug="meta_ads",
        start_date="2026-02-01",
        end_date="2026-02-28",
        version=2,
    )
    assert first.original_name == "ugly name.csv"
    assert first.file_fingerprint == fingerprint_bytes(payload)
    assert second.file_fingerprint != first.file_fingerprint
    assert first.canonical_logical_name.startswith("meta_ads__")


def test_file_series_grouping_is_deterministic(df_context) -> None:
    files = [
        register_file(
            context=df_context,
            drive_file_id=f"f{index}",
            original_name=f"meta_{index:02d}.csv",
            parent_folder_id="root_prem3",
            payload=f"date,spend\n2026-{index:02d}-01,{index}\n".encode(),
            mime_type="text/csv",
            source_slug="meta_ads",
        )
        for index in range(1, 13)
    ]
    first = group_file_series(files)
    second = group_file_series(list(reversed(files)))
    assert len(first) == 1
    assert set(first[0].file_ids) == set(second[0].file_ids)
    assert first[0].source_slug == "meta_ads"


def test_csv_parse_and_ambiguous_xlsx(df_context) -> None:
    record = register_file(
        context=df_context,
        drive_file_id="csv1",
        original_name="promo.csv",
        parent_folder_id="root_prem3",
        payload=b"start,end,name\n2026-01-01,2026-01-07,sale\n",
        mime_type="text/csv",
        source_slug="custom_regional_tv",
    )
    frame = parse_drive_payload(
        record=record,
        payload=b"start,end,name\n2026-01-01,2026-01-07,sale\n",
    )
    assert list(frame.columns) == ["start", "end", "name"]


def test_unclassified_files_group_under_custom_unclassified(df_context) -> None:
    files = [
        register_file(
            context=df_context,
            drive_file_id="mystery1",
            original_name="unknown_export.csv",
            parent_folder_id="root_prem3",
            payload=b"date,value\n2026-01-01,1\n",
            mime_type="text/csv",
        ),
        register_file(
            context=df_context,
            drive_file_id="mystery2",
            original_name="another_drop.csv",
            parent_folder_id="root_prem3",
            payload=b"date,value\n2026-02-01,2\n",
            mime_type="text/csv",
        ),
    ]
    series = group_file_series(files)
    assert len(series) == 1
    assert series[0].source_slug == "custom_unclassified"
    assert set(series[0].file_ids) == {"mystery1", "mystery2"}


def test_drive_layout_is_idempotent_under_bound_root(service, df_context, tenant_ctx) -> None:
    del tenant_ctx
    first = service.ensure_drive_layout(df_context)
    second = service.ensure_drive_layout(df_context)
    assert first.root_folder_id == "root_prem3"
    assert second.root_folder_id == first.root_folder_id
    assert first.created_at == second.created_at


def test_drive_ingest_writes_receipt_without_mutating_raw(
    service, df_context, tenant_ctx
) -> None:
    del tenant_ctx
    record = service.register_drive_file(
        df_context,
        drive_file_id="file_ingest",
        original_name="meta_spend.csv",
        parent_folder_id="root_prem3",
        payload=b"date,spend\n2026-01-01,10\n",
        mime_type="text/csv",
        source_slug="meta_ads",
    )
    candidate = service.store.put_candidate(
        SourceCandidate(
            candidate_id="dfcand_drive00000000001",
            tenant_id=df_context.tenant_id,
            workspace_id=df_context.workspace_id,
            evidence_requirement_id=None,
            location_type=LocationType.GOOGLE_DRIVE,
            resource=ResourceIdentity(
                location_type=LocationType.GOOGLE_DRIVE,
                drive_file_id=record.drive_file_id,
                drive_folder_id="root_prem3",
            ),
            group=CandidateGroup.LIKELY,
            provider_candidate="meta_ads",
            authority=ProvenanceClass.DETECTED,
        )
    )
    binding = service.bind_source(
        df_context,
        candidate_id=candidate.candidate_id,
        contract=SourceContract(grain="daily", date_field="date", date_format="YYYY-MM-DD"),
    )
    receipt = service.materialize_drive_source(
        df_context, source_id=binding.source_id, drive_file_id=record.drive_file_id
    )
    assert receipt.raw_files_modified is False
    assert receipt.files_accepted == 1
    assert receipt.destination.endswith(f"stg_{binding.source_id}")
    assert receipt.input_fingerprints["file"] == record.file_fingerprint


def test_slug_rejects_other() -> None:
    with pytest.raises(ValueError):
        provider_slug("other")
    assert canonical_logical_name(
        source_slug="google_ads",
        data_role="media",
        grain="daily",
        start_date="2026-01-01",
        end_date="2026-01-31",
        version=1,
        ext="csv",
    ).endswith(".csv")
