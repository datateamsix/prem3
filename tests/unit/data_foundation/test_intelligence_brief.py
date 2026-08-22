from tests.unit.data_foundation.conftest import acme_snapshot, seed_clean_source
from tests.unit.data_foundation.test_operate import _bind_media


def test_data_intelligence_brief_cites_structured_evidence(
    service, df_context, tenant_ctx
) -> None:
    del tenant_ctx
    binding = _bind_media(service, df_context)
    service.assess_source(df_context, binding.source_id)
    brief = service.compile_intelligence_brief(df_context)
    loaded = service.get_intelligence_brief(df_context)
    assert loaded.brief_id == brief.brief_id
    assert brief.advisory is True
    assert brief.what_prem3_found.heading == "What PreM3 found"
    assert brief.data_quality_findings.heading == "Data-quality findings"
    assert brief.prem3_can_mend.heading == "PreM3 can mend"
    assert brief.needs_your_decision.heading == "Needs your decision"
    assert brief.carries_into_premodeling.heading == "Carries into Pre-Modeling"
    assert brief.what_prem3_found.evidence_refs == brief.evidence_refs
    assert all(isinstance(item, str) and item for item in brief.evidence_refs)


def test_data_intelligence_brief_does_not_require_gemini_prose(
    service, df_context, tenant_ctx
) -> None:
    del tenant_ctx
    seed_clean_source(service)
    service.load_business_snapshot(df_context, acme_snapshot())
    brief = service.compile_intelligence_brief(df_context)
    assert brief.model_version.startswith("data-foundation/intelligence-brief/deterministic")
    assert brief.advisory is True
