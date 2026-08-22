from pathlib import Path

from app.data_foundation.proof import run_mvp_proof


def test_mvp_proof_writes_honest_machine_receipt() -> None:
    path = run_mvp_proof()
    payload = Path(path).read_text(encoding="utf-8")
    assert "DATA_FOUNDATION_READY" in payload
    assert "FOUNDATION_SOURCE_READY" in payload
    assert "BUSINESS_CONTEXT_READY" in payload
    assert "LIVE_CLOUD_PROOF_NOT_RUN" in payload
    assert "m2_11_import_ready_unchanged" in payload
    assert "foundational-intake-freeze-2026-08-22-v1" in payload
    assert "FirestoreDataFoundationStore" in payload
    assert "data-foundation/intelligence-brief/deterministic" in payload
    assert "blocker_count" in payload
