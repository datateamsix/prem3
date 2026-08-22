from app.data_foundation.enums import SourceFoundationStatus
from app.data_foundation.readiness import evaluate_source_foundation
from app.governance.import_evaluator import evaluate_import_readiness


def test_source_foundation_status_has_no_import_ready_alias() -> None:
    assert "IMPORT_READY" not in {item.value for item in SourceFoundationStatus}
    assert "READY_WITH_PREMODEL_REVIEW" not in {item.value for item in SourceFoundationStatus}
    assert SourceFoundationStatus.FOUNDATION_SOURCE_READY.value == "FOUNDATION_SOURCE_READY"
    assert SourceFoundationStatus.FOUNDATION_SOURCE_NOT_READY.value == "FOUNDATION_SOURCE_NOT_READY"


def test_m2_11_evaluator_is_the_only_import_ready_owner() -> None:
    assert evaluate_import_readiness.__doc__
    assert "Sole function" in (evaluate_import_readiness.__doc__ or "")
    assert evaluate_source_foundation.__doc__
    assert "Gemini" in (evaluate_source_foundation.__doc__ or "")
