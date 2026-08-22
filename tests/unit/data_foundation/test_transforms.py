import pandas as pd
import pytest

from app.data_foundation.enums import TransformAuthority, TransformId
from app.data_foundation.transformation.catalog import refuse_authority_promotion
from app.data_foundation.transformation.executor import apply_actions
from app.data_foundation.transformation.planner import compile_transformation_plan
from app.data_foundation.transformation.preview import preview_plan
from app.data_foundation.transformation.validator import validate_transform_output
from tests.unit.data_foundation.conftest import clean_media_frame


def test_preview_does_not_mutate_source() -> None:
    frame = clean_media_frame()
    original = frame.copy(deep=True)
    plan = compile_transformation_plan(
        source_id="dfsrc_test",
        source_fingerprint="abc",
        registry_version="v1",
        action_ids=[TransformId.DF_T006],
        output_target="acme_analytics.prem3_modeling.stg_x",
    )
    preview = preview_plan(frame, plan)
    assert frame.equals(original)
    assert preview.mutated_source is False


def test_trim_and_dedupe_are_deterministic() -> None:
    frame = pd.DataFrame(
        {"date": ["2026-01-01", "2026-01-01"], "channel": [" Search ", " Search "], "spend": [1, 1]}
    )
    plan = compile_transformation_plan(
        source_id="dfsrc_test",
        source_fingerprint="abc",
        registry_version="v1",
        action_ids=[TransformId.DF_T001, TransformId.DF_T006],
        output_target="acme_analytics.prem3_modeling.stg_x",
    )
    first = apply_actions(frame, plan, preview=True)
    second = apply_actions(frame, plan, preview=True)
    assert first.equals(second)
    assert len(first) == 1
    assert str(first.loc[0, "channel"]).strip() == "Search"
    assert frame.loc[0, "channel"] == " Search "


def test_zero_fill_and_fabricate_fail_closed() -> None:
    frame = clean_media_frame()
    zero = compile_transformation_plan(
        source_id="dfsrc_test",
        source_fingerprint="abc",
        registry_version="v1",
        action_ids=[TransformId.DF_T020],
        output_target="acme_analytics.prem3_modeling.stg_x",
        parameters={"DF-T020": {"missing_periods": ["2026-02-01"]}},
    )
    with pytest.raises(ValueError, match="MISSING != ZERO"):
        apply_actions(frame, zero, preview=True)
    fabricate = compile_transformation_plan(
        source_id="dfsrc_test",
        source_fingerprint="abc",
        registry_version="v1",
        action_ids=[TransformId.DF_T021],
        output_target="acme_analytics.prem3_modeling.stg_x",
    )
    with pytest.raises(PermissionError, match="Fabricating"):
        apply_actions(frame, fabricate, preview=True)


def test_agent_cannot_promote_authority() -> None:
    with pytest.raises(PermissionError, match="AUTO_SAFE"):
        refuse_authority_promotion(TransformId.DF_T014, TransformAuthority.AUTO_SAFE)


def test_user_required_cannot_auto_run() -> None:
    frame = clean_media_frame()
    plan = compile_transformation_plan(
        source_id="dfsrc_test",
        source_fingerprint="abc",
        registry_version="v1",
        action_ids=[TransformId.DF_T015],
        output_target="acme_analytics.prem3_modeling.stg_x",
    )
    with pytest.raises(PermissionError, match="user decision"):
        apply_actions(frame, plan, preview=False)


def test_validator_rejects_source_destination() -> None:
    frame = clean_media_frame()
    plan = compile_transformation_plan(
        source_id="raw",
        source_fingerprint="abc",
        registry_version="v1",
        action_ids=[TransformId.DF_T006],
        output_target="customer.raw_source",
    )
    output = apply_actions(frame, plan, preview=True)
    proof = validate_transform_output(source=frame, output=output, plan=plan)
    assert proof["source_unchanged"] is True
    with pytest.raises(ValueError):
        validate_transform_output(source=output, output=output, plan=plan)
