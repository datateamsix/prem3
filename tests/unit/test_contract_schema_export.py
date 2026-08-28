"""Deterministic JSON Schema export and contract drift gate."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.state import RunStage
from app.core.tenancy import TenantContext, WorkspaceContext
from app.intelligence.contracts import KnowledgeClass
from app.mel.models import LearningReceiptEnum
from app.tools.schema_export import (
    DEFAULT_SCHEMA_DIR,
    MANIFEST_NAME,
    SCHEMA_FAMILIES,
    check_schema_artifacts,
    render_schema_artifacts,
    sha256_bytes,
    write_schema_artifacts,
)

REQUIRED_ARTIFACTS = (
    "response.schema.json",
    "state.schema.json",
    "intelligence.schema.json",
    "mel.schema.json",
    "api.schema.json",
    "planning.schema.json",
    MANIFEST_NAME,
)


def test_contract_export_is_deterministic(tmp_path: Path) -> None:
    first = write_schema_artifacts(tmp_path / "a")
    second = write_schema_artifacts(tmp_path / "b")
    assert first.keys() == second.keys()
    for name in first:
        assert first[name] == second[name]
        assert first[name] == (tmp_path / "a" / name).read_bytes()
        assert second[name] == (tmp_path / "b" / name).read_bytes()
    again = render_schema_artifacts()
    assert again == first


def test_committed_contracts_match_models() -> None:
    generated = render_schema_artifacts()
    assert set(generated) == set(REQUIRED_ARTIFACTS)
    errors = check_schema_artifacts(DEFAULT_SCHEMA_DIR)
    assert errors == [], errors
    for name, payload in generated.items():
        committed = (DEFAULT_SCHEMA_DIR / name).read_bytes().replace(b"\r\n", b"\n")
        assert committed == payload
        assert payload.endswith(b"\n")
        assert b"\r" not in payload


def test_contract_drift_is_detected(tmp_path: Path) -> None:
    write_schema_artifacts(tmp_path)
    assert check_schema_artifacts(tmp_path) == []
    stale = tmp_path / "response.schema.json"
    stale.write_bytes(stale.read_bytes() + b" ")
    errors = check_schema_artifacts(tmp_path)
    assert "stale: response.schema.json" in errors
    missing_dir = tmp_path / "empty"
    missing_dir.mkdir()
    missing_errors = check_schema_artifacts(missing_dir)
    assert "missing: response.schema.json" in missing_errors


def test_exported_roots_preserve_authoritative_enums() -> None:
    artifacts = render_schema_artifacts()
    response = artifacts["response.schema.json"].decode("utf-8")
    state = artifacts["state.schema.json"].decode("utf-8")
    intelligence = artifacts["intelligence.schema.json"].decode("utf-8")
    mel = artifacts["mel.schema.json"].decode("utf-8")

    assert "MODEL_READY" in response
    assert "OFFICIAL_MERIDIAN" in response
    assert "gate_evidence" in response
    assert "MERIDIAN_NORMATIVE" in response

    for stage in RunStage:
        assert stage.value in state
    assert "WAITING_FOR_APPROVAL" in state
    assert "WAITING_FOR_MODEL_APPROVAL" in state
    assert "MODELING" in state
    assert "scratch_dir" in state

    for knowledge in KnowledgeClass:
        assert knowledge.value in intelligence
    assert "PREM3_PRE_EDA" in intelligence

    assert LearningReceiptEnum.EXPERIENCE_LEARNED.value in mel
    assert LearningReceiptEnum.EXPERIENCE_APPLIED.value in mel
    assert "operational_authority" in mel
    assert "SEALED_HOLDOUT" in mel
    assert "app_mel_models__CandidateLesson" not in mel
    assert "app_mel_models__LessonEvaluation" not in mel


def test_manifest_hashes_match_serialized_schema_bytes() -> None:
    artifacts = render_schema_artifacts()
    manifest = json.loads(artifacts[MANIFEST_NAME].decode("utf-8"))
    assert manifest["hash_algorithm"] == "sha256"
    assert "timestamp" not in manifest
    assert "generated_at" not in manifest
    families = {item["artifact"]: item for item in manifest["families"]}
    for family in SCHEMA_FAMILIES:
        item = families[family.artifact]
        assert item["sha256"] == sha256_bytes(artifacts[family.artifact])
        assert item["public_roots"] == [model.__name__ for model in family.roots]
        assert item["python_module"] == family.python_module


def test_tenant_and_workspace_context_are_not_public_schema_roots() -> None:
    roots = {model for family in SCHEMA_FAMILIES for model in family.roots}
    assert TenantContext not in roots
    assert WorkspaceContext not in roots
