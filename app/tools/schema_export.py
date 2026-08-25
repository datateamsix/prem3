"""Deterministic JSON Schema export for public PreM3 backend contracts.

Generates committed artifacts under ``contracts/schema/``. Does not change
runtime models, gates, or persistence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from app.core.contracts import (
    BigQueryPublishReceipt,
    DurableRunState,
    Issue,
    LearningReceipt,
    ReadinessReceipt,
    RunStatusEvent,
    Transformation,
)
from app.domain.intelligence.models import DomainView, DomainViewDiff
from app.intelligence.contracts import (
    DimensionalStatus,
    GuidedRemediationItem,
    Prem3PreEdaFinding,
    SemanticQuestion,
)
from app.mel.models import (
    ExperienceApplication,
    ExperienceEpisode,
    ExperienceReflection,
    HoldoutManifest,
    PromotionReceipt,
)
from app.response.contracts import StructuredResponse
from app.service.errors import ProblemDetail
from app.service.mmm_models import (
    CreateModelDesignRequest,
    FitRunResponse,
    MMMSummaryResponse,
    ModelVersionResponse,
)
from app.modeling.mmm.results.read_models import (
    DecisionBriefResponse,
    MmmResponseCurvesResponse,
    MmmResultsReadModelResponse,
)
from app.service.models import (
    BigQueryBindingResponse,
    BillingSessionResponse,
    CheckoutSessionRequest,
    CreateDatasetRequest,
    CreateWorkspaceRequest,
    DatasetImportBindingRequest,
    DatasetImportBindingResponse,
    DatasetListResponse,
    DatasetResponse,
    DriveBindingResponse,
    GoogleConnectionResponse,
    GoogleOAuthStartRequest,
    GoogleOAuthStartResponse,
    ImportReadinessReceiptResponse,
    MeResponse,
    PlanCatalogResponse,
    PortalSessionRequest,
    PublishExecutionListResponse,
    PublishExecutionResponse,
    PublishReadinessReceiptResponse,
    SourceMaterializationListResponse,
    SourceMaterializationResponse,
    WebhookAckResponse,
    WorkspaceListResponse,
    WorkspaceResponse,
)
from app.service.project_models import (
    BusinessIqOverviewReadModel,
    CreateProjectRequest,
    DataFoundationOverviewReadModel,
    ProjectHomeReadModel,
    ProjectListResponse,
    ProjectResponse,
)

JSON_SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"
EXPORT_VERSION = "1.0.0"
SCHEMA_DIRNAME = "contracts/schema"
MANIFEST_NAME = "manifest.json"

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA_DIR = REPO_ROOT / "contracts" / "schema"


class SchemaExportError(ValueError):
    """Fail-closed schema export or $defs collision."""


@dataclass(frozen=True, slots=True)
class SchemaFamily:
    artifact: str
    family: str
    title: str
    description: str
    python_module: str
    roots: tuple[type[BaseModel], ...]
    composition: Literal["single_root", "catalog"]


SCHEMA_FAMILIES: tuple[SchemaFamily, ...] = (
    SchemaFamily(
        artifact="response.schema.json",
        family="response",
        title="PreM3 structured response",
        description=(
            "Typed presentation contract. Public root is StructuredResponse; "
            "nested models live in $defs. Machine structure is authoritative; "
            "Markdown is a renderer."
        ),
        python_module="app.response.contracts",
        roots=(StructuredResponse,),
        composition="single_root",
    ),
    SchemaFamily(
        artifact="state.schema.json",
        family="state",
        title="PreM3 run state contracts",
        description=(
            "Operational run contracts from app.core.contracts / app.core.state. "
            "Public roots are catalogued with oneOf. RunStage includes off-golden-path "
            "values WAITING_FOR_APPROVAL, WAITING_FOR_MODEL_APPROVAL, and MODELING. "
            "DurableRunState is the persisted run metadata root, including operational "
            "fields such as scratch_dir that the frontend RunSummary composition type "
            "does not render."
        ),
        python_module="app.core.contracts",
        roots=(
            DurableRunState,
            RunStatusEvent,
            Issue,
            Transformation,
            ReadinessReceipt,
            BigQueryPublishReceipt,
            LearningReceipt,
        ),
        composition="catalog",
    ),
    SchemaFamily(
        artifact="intelligence.schema.json",
        family="intelligence",
        title="PreM3 run intelligence contracts",
        description=(
            "Presentation/integration models from app.intelligence.contracts plus "
            "DOMAIN_VIEW payloads from app.domain.intelligence.models. KnowledgeClass "
            "on Prem3PreEdaFinding is the run-intelligence enum "
            "(MERIDIAN_NORMATIVE, PREM3_DETERMINISTIC_DIAGNOSTIC, "
            "MMM_EVIDENCE_HEURISTIC, MMM_JUDGMENT, PREM3_POLICY_BLOCKER, "
            "DOMAIN_VIEW_LEARNED). DomainView uses a distinct DOMAIN_VIEW "
            "KnowledgeClass; those definitions are namespaced in $defs."
        ),
        python_module="app.intelligence.contracts",
        roots=(
            Prem3PreEdaFinding,
            SemanticQuestion,
            GuidedRemediationItem,
            DimensionalStatus,
            DomainView,
            DomainViewDiff,
        ),
        composition="catalog",
    ),
    SchemaFamily(
        artifact="mel.schema.json",
        family="mel",
        title="PreM3 MEL experience contracts",
        description=(
            "Presentation/integration MEL structures. Memory is not reflection; "
            "reflection has no operational authority; EXPERIENCE_LEARNED is a "
            "promoted-lesson receipt; EXPERIENCE_APPLIED is a later independent "
            "behavior-change proof. CandidateLesson / LessonEvaluation internals "
            "are not exported."
        ),
        python_module="app.mel.models",
        roots=(
            ExperienceEpisode,
            ExperienceReflection,
            PromotionReceipt,
            ExperienceApplication,
            HoldoutManifest,
        ),
        composition="catalog",
    ),
    SchemaFamily(
        artifact="api.schema.json",
        family="api",
        title="PreM3 prem3-api presentation contracts",
        description=(
            "Presentation-safe HTTP contracts for prem3-api. Persistence / "
            "Firestore models are not exported. Clerk identity is implemented; "
            "Stripe adapters remain pending."
        ),
        python_module="app.service.models",
        roots=(
            ProblemDetail,
            MeResponse,
            PlanCatalogResponse,
            WorkspaceResponse,
            CreateWorkspaceRequest,
            WorkspaceListResponse,
            DatasetResponse,
            CreateDatasetRequest,
            DatasetListResponse,
            CheckoutSessionRequest,
            PortalSessionRequest,
            BillingSessionResponse,
            WebhookAckResponse,
            GoogleOAuthStartRequest,
            GoogleOAuthStartResponse,
            GoogleConnectionResponse,
            DriveBindingResponse,
            BigQueryBindingResponse,
            DatasetImportBindingRequest,
            DatasetImportBindingResponse,
            ImportReadinessReceiptResponse,
            PublishReadinessReceiptResponse,
            SourceMaterializationResponse,
            SourceMaterializationListResponse,
            PublishExecutionResponse,
            PublishExecutionListResponse,
            ProjectResponse,
            CreateProjectRequest,
            ProjectListResponse,
            ProjectHomeReadModel,
            BusinessIqOverviewReadModel,
            DataFoundationOverviewReadModel,
            MMMSummaryResponse,
            CreateModelDesignRequest,
            ModelVersionResponse,
            FitRunResponse,
            MmmResultsReadModelResponse,
            MmmResponseCurvesResponse,
            DecisionBriefResponse,
        ),
        composition="catalog",
    ),
)


def _canonicalize(value: Any) -> Any:
    """Recursively sort object keys. List order is preserved (enums are semantic)."""
    if isinstance(value, dict):
        return {key: _canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    return value


def _encode(schema: dict[str, Any]) -> bytes:
    canonical = _canonicalize(schema)
    text = json.dumps(canonical, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    return text.encode("utf-8")


def _rewrite_refs(node: Any, mapping: dict[str, str]) -> Any:
    if isinstance(node, dict):
        rewritten: dict[str, Any] = {}
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str) and value.startswith("#/$defs/"):
                name = value.removeprefix("#/$defs/")
                rewritten[key] = f"#/$defs/{mapping.get(name, name)}"
            else:
                rewritten[key] = _rewrite_refs(value, mapping)
        return rewritten
    if isinstance(node, list):
        return [_rewrite_refs(item, mapping) for item in node]
    return node


def _module_prefix(model: type[BaseModel]) -> str:
    return model.__module__.replace(".", "_")


def _model_def_name(model: type[BaseModel]) -> str:
    return f"{_module_prefix(model)}__{model.__name__}"


def _collect_model_schema(model: type[BaseModel]) -> tuple[str, dict[str, Any], dict[str, Any]]:
    raw = model.model_json_schema(mode="serialization")
    nested = dict(raw.pop("$defs", {}))
    prefix = _module_prefix(model)
    def_name = _model_def_name(model)
    mapping = {name: f"{prefix}__{name}" for name in nested}
    mapping[model.__name__] = def_name
    # Nested defs from Pydantic use unqualified class names. Qualify by the
    # exporting root model's module so DomainView and run-intelligence
    # KnowledgeClass enums cannot collide inside one artifact.
    qualified_nested: dict[str, Any] = {}
    for name, body in nested.items():
        qualified_nested[mapping[name]] = _rewrite_refs(body, mapping)
    root_body = _rewrite_refs(raw, mapping)
    return def_name, root_body, qualified_nested


def build_family_schema(family: SchemaFamily) -> dict[str, Any]:
    defs: dict[str, Any] = {}
    root_names: list[str] = []
    for model in family.roots:
        def_name, root_body, nested = _collect_model_schema(model)
        for name, body in nested.items():
            existing = defs.get(name)
            if existing is not None and existing != body:
                raise SchemaExportError(f"Conflicting $defs entry {name!r} in {family.artifact}")
            defs[name] = body
        if def_name in defs and defs[def_name] != root_body:
            raise SchemaExportError(
                f"Conflicting root $defs entry {def_name!r} in {family.artifact}"
            )
        defs[def_name] = root_body
        root_names.append(def_name)

    schema: dict[str, Any] = {
        "$schema": JSON_SCHEMA_DRAFT,
        "title": family.title,
        "description": family.description,
        "$defs": defs,
    }
    if family.composition == "single_root":
        schema["$ref"] = f"#/$defs/{root_names[0]}"
    else:
        schema["oneOf"] = [{"$ref": f"#/$defs/{name}"} for name in root_names]
    return schema


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def render_schema_artifacts() -> dict[str, bytes]:
    """Return artifact filename -> UTF-8 JSON bytes (LF, trailing newline)."""
    artifacts: dict[str, bytes] = {}
    manifest_families: list[dict[str, Any]] = []
    for family in SCHEMA_FAMILIES:
        payload = _encode(build_family_schema(family))
        artifacts[family.artifact] = payload
        manifest_families.append(
            {
                "artifact": family.artifact,
                "family": family.family,
                "public_roots": [model.__name__ for model in family.roots],
                "python_module": family.python_module,
                "python_qualnames": [
                    f"{model.__module__}.{model.__name__}" for model in family.roots
                ],
                "composition": family.composition,
                "sha256": sha256_bytes(payload),
            }
        )
    manifest = {
        "export_version": EXPORT_VERSION,
        "schema_format": JSON_SCHEMA_DRAFT,
        "hash_algorithm": "sha256",
        "hash_input": "final UTF-8 serialized schema bytes including trailing newline",
        "families": manifest_families,
    }
    artifacts[MANIFEST_NAME] = _encode(manifest)
    return artifacts


def write_schema_artifacts(dest: Path) -> dict[str, bytes]:
    dest.mkdir(parents=True, exist_ok=True)
    artifacts = render_schema_artifacts()
    for name, payload in artifacts.items():
        (dest / name).write_bytes(payload)
    return artifacts


def check_schema_artifacts(dest: Path) -> list[str]:
    """Return human-readable drift errors. Never writes."""
    generated = render_schema_artifacts()
    errors: list[str] = []
    if not dest.is_dir():
        return [f"missing schema directory: {dest}"]
    committed = {path.name for path in dest.glob("*.json")}
    expected = set(generated)
    for name in sorted(expected - committed):
        errors.append(f"missing: {name}")
    for name in sorted(committed - expected):
        errors.append(f"unexpected: {name}")
    for name in sorted(expected & committed):
        existing = (dest / name).read_bytes().replace(b"\r\n", b"\n")
        if existing != generated[name]:
            errors.append(f"stale: {name}")
    return errors
