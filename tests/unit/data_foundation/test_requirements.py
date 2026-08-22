from app.data_foundation.discovery.requirements import compile_evidence_requirements
from app.data_foundation.enums import CoverageState, EvidenceRequirementType
from tests.unit.data_foundation.conftest import acme_snapshot


def test_compiler_inherits_business_iq_concepts(tenant_ctx) -> None:
    del tenant_ctx
    compiled = compile_evidence_requirements(acme_snapshot())
    types = {item.requirement_type for item in compiled.requirements}
    concepts = {item.concept for item in compiled.requirements}
    assert EvidenceRequirementType.KPI in types
    assert EvidenceRequirementType.MEDIA in types
    assert "Paid Search" in concepts
    assert "Promotions" in concepts
    seasonality = next(item for item in compiled.requirements if item.concept == "Seasonality")
    assert seasonality.coverage_state is CoverageState.PREM3_PROVIDED


def test_compiler_rejects_unready_snapshot() -> None:
    snapshot = acme_snapshot().model_copy(update={"business_context_ready": False})
    try:
        compile_evidence_requirements(snapshot)
    except ValueError as exc:
        assert "BUSINESS_CONTEXT_READY" in str(exc)
    else:
        raise AssertionError("expected ValueError")
