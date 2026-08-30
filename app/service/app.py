"""prem3-api application factory.

Local default is in-memory and fail-closed unless Clerk/Stripe settings
are present. Cloud runtime (PREM3_API_RUNTIME=cloud or Cloud Run K_SERVICE)
constructs Firestore, Clerk, and Stripe from deployment configuration.
No Firestore, Clerk, or Stripe network call on import.
"""

from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.business_iq.service import BusinessIqService
from app.config import Settings, load_settings
from app.control_plane.firestore_repo import FirestoreControlPlaneRepository
from app.control_plane.repository import ControlPlaneRepository
from app.data_foundation.service import DataFoundationService
from app.data_foundation.warehouse import FoundationWarehouse
from app.eda.repository import FirestoreExtendedEDARepository, InMemoryExtendedEDARepository
from app.eda.service import ExtendedEDAService
from app.integrations.google.adapters import (
    FakeBigQueryClient,
    FakeDriveClient,
    RestBigQueryClient,
    RestDriveClient,
    RestGoogleOAuthProvider,
)
from app.integrations.google.vault import (
    CloudKmsKek,
    ControlPlaneCredentialVault,
    InMemoryCredentialVault,
)
from app.investment_optimization.accepted_model import ModelingRepositoryDirectory
from app.investment_optimization.adapter import NativeMeridianFixedBudgetAdapter
from app.investment_optimization.advanced_service import AdvancedOptimizationService
from app.investment_optimization.consumption import MemoryModelConsumptionSource
from app.investment_optimization.firestore import FirestoreOptimizationMetadataStore
from app.investment_optimization.proposal import ProposalGovernanceService
from app.investment_optimization.risk.service import RiskFrontierService
from app.investment_optimization.run_service import OptimizationRunService
from app.investment_optimization.service import OptimizationReadinessService
from app.investment_optimization.simulation.execution import UnavailableSimulationExecutionAdapter
from app.investment_optimization.simulation.service import SimulationService
from app.investment_optimization.store import InMemoryOptimizationMetadataStore
from app.investment_planning.actuals import DataFoundationActualSpendAdapter
from app.investment_planning.bigquery_actuals import BigQueryActualSpendAdapter
from app.investment_planning.errors import PlanningError
from app.investment_planning.exposure_service import ExposureRiskService
from app.investment_planning.firestore import FirestoreInvestmentPlanningStore
from app.investment_planning.markets import IdentityGraphMarketDirectory
from app.investment_planning.outcomes.service import OutcomeService
from app.investment_planning.service import InvestmentPlanService
from app.investment_planning.store import InMemoryInvestmentPlanningMetadataStore
from app.materialization.canonical_gate import CanonicalFoundationSourceGate
from app.materialization.foundation_compat import FoundationSourceGate
from app.materialization.service import MaterializationService
from app.modeling.mmm.dispatch import CloudTasksFitDispatcher
from app.modeling.mmm.firestore import FirestoreModelingRepository
from app.modeling.mmm.service import MMMModelingService
from app.modeling.mta.service import MTAService
from app.publish_execution.model_ready import (
    ModelReadyEvidenceResolver,
    NullModelReadyEvidenceResolver,
)
from app.publish_execution.service import PublishExecutionService
from app.service.auth import IdentityVerifier, UnconfiguredIdentityVerifier
from app.service.billing import BillingGateway, UnavailableBillingGateway
from app.service.billing_config import BillingConfig
from app.service.billing_events import BillingWebhookProcessor
from app.service.catalog import build_plan_catalog
from app.service.clerk_runtime import (
    MembershipAuthority,
    OrganizationDirectory,
    RealClerkRuntime,
    WebhookVerifier,
)
from app.service.errors import (
    APIError,
    ProblemDetail,
    ProblemFieldError,
    internal_error,
    planning_error,
    problem_json,
    validation_error,
)
from app.service.evaluation_dispatch import (
    CloudTasksEvaluationDispatcher,
    EvaluationDispatcher,
    FakeEvaluationDispatcher,
    UnavailableEvaluationDispatcher,
)
from app.service.evaluation_jobs import (
    CloudRunEvaluationJobLauncher,
    EvaluationJobLauncher,
    FakeEvaluationJobLauncher,
    UnavailableEvaluationJobLauncher,
)
from app.service.evaluation_launch import EvaluationLaunchService
from app.service.evaluation_service import DEFAULT_EVALUATION_JOB_NAME, EvaluationService
from app.service.google_bigquery import BigQueryBindingService
from app.service.google_drive import DriveBindingService
from app.service.google_oauth import GoogleConnectionService
from app.service.import_governance import ImportGovernanceService
from app.service.middleware import RequestIdMiddleware, current_request_id
from app.service.models import PlanCatalogResponse
from app.service.object_store import FakeObjectStore, GcsObjectStore, ObjectStore
from app.service.product_stores import build_identity_graph_store, build_product_stores
from app.service.publish_governance import PublishGovernanceService
from app.service.routers import (
    billing,
    business_iq,
    catalog,
    data_foundation,
    datasets,
    evaluations,
    exposure_risk,
    google_integrations,
    google_oauth,
    health,
    identity,
    identity_webhooks,
    import_governance,
    internal_dispatch,
    investment_planning,
    investment_portfolio,
    materializations,
    mmm,
    mta,
    outcomes,
    projects,
    publishes,
    risk_frontier,
    runs,
    simulation,
    uploads,
    workspaces,
)
from app.service.runtime import assert_provider_mode_safe, build_control_plane, uses_cloud_runtime
from app.service.service_identity import (
    FakeServiceIdentityVerifier,
    GoogleOidcServiceIdentityVerifier,
    ServiceIdentityVerifier,
)
from app.service.stripe_gateway import StripeBillingGateway
from app.service.stripe_provider import RealStripeProvider
from app.service.upload_config import UploadConfig
from app.service.upload_service import UploadService
from app.service.upload_signing import FakeUploadSigner, GcsV4UploadSigner, UploadSigner


def create_app(
    *,
    settings: Settings | None = None,
    control_plane_repository: ControlPlaneRepository | None = None,
    identity_verifier: IdentityVerifier | None = None,
    billing_gateway: BillingGateway | None = None,
    billing_webhook_processor: BillingWebhookProcessor | None = None,
    plan_catalog: PlanCatalogResponse | None = None,
    membership_authority: MembershipAuthority | None = None,
    webhook_verifier: WebhookVerifier | None = None,
    organization_directory: OrganizationDirectory | None = None,
    upload_service: UploadService | None = None,
    evaluation_service: EvaluationService | None = None,
    evaluation_dispatcher: EvaluationDispatcher | None = None,
    evaluation_job_launcher: EvaluationJobLauncher | None = None,
    service_identity_verifier: ServiceIdentityVerifier | None = None,
    upload_signer: UploadSigner | None = None,
    object_store: ObjectStore | None = None,
    google_oauth_provider=None,
    google_credential_vault=None,
    google_drive_client=None,
    google_bigquery_client=None,
    foundation_source_gate: FoundationSourceGate | None = None,
    model_ready_resolver: ModelReadyEvidenceResolver | None = None,
    mmm_modeling: MMMModelingService | None = None,
    mmm_fit_launcher=None,
    extended_eda: ExtendedEDAService | None = None,
) -> FastAPI:
    cfg = settings or load_settings()
    assert_provider_mode_safe(cfg)
    clerk_runtime = None
    if identity_verifier is None and cfg.clerk_secret_key:
        clerk_runtime = RealClerkRuntime(cfg)
        identity_verifier = clerk_runtime
        if membership_authority is None:
            membership_authority = clerk_runtime
        if webhook_verifier is None:
            webhook_verifier = clerk_runtime
        if organization_directory is None:
            organization_directory = clerk_runtime
    app = FastAPI(
        title="prem3-api",
        version="0.1.0",
        summary="PreM3 authenticated product API",
        description=(
            "Presentation-safe Project, Dataset, upload, Evaluation, catalog, billing, "
            "Google connection, import/publish governance, Business IQ, "
            "Data Foundation, and governed MMM modeling contracts. Clerk session "
            "tokens are verified when the identity provider is configured. Creating "
            "an Evaluation returns 202 Accepted only after durable Cloud Tasks "
            "enqueue; 202 is not ADK completion and not MODEL_READY. Posterior "
            "sampling is never autonomous and requires an exact fingerprinted "
            "FitPlan approval. Tenant identity is never accepted from the client. "
            "IMPORT_READY, FOUNDATION_SOURCE_READY, DATA_FOUNDATION_READY, "
            "MODEL_READY, MODEL_ACCEPTED, and PUBLISH_READY are distinct "
            "deterministic states."
        ),
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = cfg
    repo, control_plane_status = build_control_plane(cfg, control_plane_repository)
    app.state.control_plane = repo
    app.state.control_plane_status = control_plane_status
    app.state.identity_verifier = identity_verifier or UnconfiguredIdentityVerifier()
    app.state.membership_authority = membership_authority
    app.state.webhook_verifier = webhook_verifier
    app.state.organization_directory = organization_directory
    app.state.clerk_runtime = clerk_runtime
    billing_config = BillingConfig.from_settings(cfg)
    app.state.billing_config = billing_config
    if billing_gateway is None and cfg.stripe_secret_key:
        provider = RealStripeProvider(billing_config)
        billing_gateway = StripeBillingGateway(provider=provider, repo=repo, config=billing_config)
        if billing_webhook_processor is None and cfg.stripe_webhook_secret:
            billing_webhook_processor = BillingWebhookProcessor(
                provider=provider, repo=repo, config=billing_config
            )
    app.state.billing_gateway = billing_gateway or UnavailableBillingGateway()
    app.state.billing_webhook_processor = billing_webhook_processor
    app.state.plan_catalog = plan_catalog or build_plan_catalog(config=billing_config)
    dispatcher, launcher, service_identity, job_name = _default_evaluation_stack(
        cfg,
        dispatcher=evaluation_dispatcher,
        launcher=evaluation_job_launcher,
        verifier=service_identity_verifier,
    )
    app.state.evaluation_dispatcher = dispatcher
    app.state.evaluation_job_launcher = launcher
    app.state.service_identity_verifier = service_identity
    app.state.evaluation_service = evaluation_service or EvaluationService(
        repo=repo, dispatcher=dispatcher, job_name=job_name
    )
    app.state.evaluation_launch = EvaluationLaunchService(repo=repo, launcher=launcher)
    app.state.upload_service = upload_service or _default_upload_service(
        cfg, repo, signer=upload_signer, object_store=object_store
    )
    local_vault = google_credential_vault
    if local_vault is None and not uses_cloud_runtime():
        local_vault = InMemoryCredentialVault()
    google_services = _default_google_services(
        cfg,
        repo,
        oauth_provider=google_oauth_provider,
        vault=local_vault,
        drive_client=google_drive_client,
        bigquery_client=google_bigquery_client,
        model_ready_resolver=model_ready_resolver,
    )
    app.state.google_connections = google_services["connections"]
    app.state.drive_bindings = google_services["drive"]
    app.state.bigquery_bindings = google_services["bigquery"]
    app.state.import_governance = google_services["import_governance"]
    app.state.publish_governance = google_services["publish_governance"]
    app.state.model_ready_resolver = google_services["model_ready"]
    app.state.google_oauth_provider = google_services["oauth"]
    app.state.google_credential_vault = google_services["vault"]
    app.state.google_drive_client = google_services["drive_client"]
    app.state.google_bigquery_client = google_services["bq_client"]
    business_iq_store, data_foundation_store = build_product_stores(repo)
    app.state.business_iq_store = business_iq_store
    app.state.data_foundation_store = data_foundation_store
    app.state.business_iq = BusinessIqService(store=business_iq_store)
    app.state.data_foundation = DataFoundationService(
        store=data_foundation_store,
        warehouse=FoundationWarehouse(),
        bigquery_client=google_services["bq_client"],
        drive_client=google_services["drive_client"],
    )
    identity_graph_store = build_identity_graph_store(repo)
    if isinstance(repo, FirestoreControlPlaneRepository):
        planning_store = FirestoreInvestmentPlanningStore(repo.client)
    else:
        planning_store = InMemoryInvestmentPlanningMetadataStore()
    app.state.identity_graph_store = identity_graph_store
    app.state.investment_planning_store = planning_store
    app.state.exposure_risk = ExposureRiskService(planning_store)
    app.state.investment_planning = InvestmentPlanService(
        repo=repo,
        store=planning_store,
        drive=google_services["drive_client"],
        connections=google_services["connections"],
        drive_bindings=google_services["drive"],
        business_iq=business_iq_store,
        markets=IdentityGraphMarketDirectory(identity_graph_store),
        actuals=DataFoundationActualSpendAdapter(
            data_foundation_store,
            rows=BigQueryActualSpendAdapter(
                data_foundation_store,
                bigquery=google_services["bq_client"],
                repo=repo,
                connections=google_services["connections"],
            ),
        ),
    )
    if isinstance(repo, FirestoreControlPlaneRepository):
        optimization_store = FirestoreOptimizationMetadataStore(repo.client)
    else:
        optimization_store = InMemoryOptimizationMetadataStore()
    app.state.optimization_store = optimization_store
    app.state.optimization_consumption = MemoryModelConsumptionSource()
    if foundation_source_gate is None:
        foundation_source_gate = CanonicalFoundationSourceGate(data_foundation_store)
    upload = app.state.upload_service
    app.state.materialization = MaterializationService(
        repo=repo,
        import_governance=google_services["import_governance"],
        upload_service=upload,
        connections=google_services["connections"],
        drive=google_services["drive_client"],
        bigquery=google_services["bq_client"],
        object_store=upload._store,
        upload_config=upload._config,
        foundation_gate=foundation_source_gate,
    )
    app.state.publish_execution = PublishExecutionService(
        repo=repo,
        publish_governance=google_services["publish_governance"],
        connections=google_services["connections"],
        drive=google_services["drive_client"],
        bigquery=google_services["bq_client"],
        model_ready=google_services["model_ready"],
    )
    modeling, fit_launcher = _default_mmm_stack(
        cfg,
        repo,
        modeling=mmm_modeling,
        launcher=mmm_fit_launcher,
    )
    app.state.mmm_modeling = modeling
    app.state.mmm_fit_launcher = fit_launcher
    app.state.optimization_readiness = OptimizationReadinessService(
        repo=repo,
        store=optimization_store,
        planning=app.state.investment_planning,
        models=ModelingRepositoryDirectory(modeling.repo),
        consumption=app.state.optimization_consumption,
    )
    upload_store = getattr(app.state.upload_service, "_store", None)
    app.state.optimization_runs = OptimizationRunService(
        repo=repo,
        store=optimization_store,
        planning=app.state.investment_planning,
        models=ModelingRepositoryDirectory(modeling.repo),
        consumption=app.state.optimization_consumption,
        object_store=upload_store or FakeObjectStore(),
        artifact_bucket=cfg.artifact_bucket or "prem3-test-artifacts",
        optimizer=NativeMeridianFixedBudgetAdapter(),
        execute_inline=not uses_cloud_runtime(),
    )
    app.state.risk_frontier = RiskFrontierService(optimization_store)
    app.state.simulation = SimulationService(
        optimization_store,
        adapter=UnavailableSimulationExecutionAdapter(),
        object_store=upload_store or FakeObjectStore(),
        artifact_bucket=cfg.artifact_bucket or "prem3-test-artifacts",
    )
    app.state.outcomes = OutcomeService(optimization_store)
    app.state.advanced_optimization = AdvancedOptimizationService(
        repo=repo,
        store=optimization_store,
        object_store=upload_store or FakeObjectStore(),
        artifact_bucket=cfg.artifact_bucket or "prem3-test-artifacts",
    )
    app.state.proposal_governance = ProposalGovernanceService(
        repo=repo,
        store=optimization_store,
        runs=app.state.optimization_runs,
        object_store=upload_store or FakeObjectStore(),
        artifact_bucket=cfg.artifact_bucket or "prem3-test-artifacts",
        planning=app.state.investment_planning,
        models=ModelingRepositoryDirectory(modeling.repo),
    )
    app.state.mta_service = MTAService()
    app.state.mmm_service_identity_verifier = _mmm_service_identity_verifier(cfg)
    if extended_eda is None:
        if uses_cloud_runtime():
            client = getattr(repo, "client", None)
            eda_repo = (
                FirestoreExtendedEDARepository(client)
                if client is not None
                else InMemoryExtendedEDARepository()
            )
            extended_eda = ExtendedEDAService(eda_repo)
        else:
            extended_eda = ExtendedEDAService()
    app.state.extended_eda = extended_eda

    app.add_middleware(RequestIdMiddleware)
    app.include_router(health.router)
    app.include_router(catalog.router)
    app.include_router(identity.router)
    app.include_router(workspaces.router)
    app.include_router(projects.router)
    app.include_router(datasets.router)
    app.include_router(uploads.router)
    app.include_router(evaluations.router)
    app.include_router(runs.router)
    app.include_router(google_oauth.router)
    app.include_router(google_integrations.router)
    app.include_router(import_governance.router)
    app.include_router(business_iq.router)
    app.include_router(data_foundation.router)
    app.include_router(investment_planning.canonical_router)
    app.include_router(investment_planning.workspace_alias_router)
    app.include_router(investment_portfolio.canonical_portfolio_router)
    app.include_router(investment_portfolio.workspace_alias_portfolio_router)
    app.include_router(exposure_risk.canonical_exposure_router)
    app.include_router(exposure_risk.workspace_alias_exposure_router)
    app.include_router(risk_frontier.canonical_risk_frontier_router)
    app.include_router(risk_frontier.workspace_alias_risk_frontier_router)
    app.include_router(simulation.canonical_simulation_router)
    app.include_router(simulation.workspace_alias_simulation_router)
    app.include_router(outcomes.canonical_outcomes_router)
    app.include_router(outcomes.workspace_alias_outcomes_router)
    app.include_router(materializations.router)
    app.include_router(publishes.router)
    app.include_router(mmm.router)
    app.include_router(mta.router)
    app.include_router(billing.router)
    app.include_router(identity_webhooks.router)
    app.include_router(internal_dispatch.router)

    @app.exception_handler(PlanningError)
    async def planning_error_handler(request: Request, exc: PlanningError) -> JSONResponse:
        problem = planning_error(exc).to_problem(
            request_id=_request_id(), instance=str(request.url.path)
        )
        return _problem_response(problem)

    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
        problem = exc.to_problem(request_id=_request_id(), instance=str(request.url.path))
        return _problem_response(problem)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields: list[ProblemFieldError] = []
        for err in exc.errors():
            loc = ".".join(str(part) for part in err.get("loc", ()) if part != "body")
            fields.append(ProblemFieldError(field=loc or "body", message=str(err.get("msg", ""))))
        problem = validation_error(fields).to_problem(
            request_id=_request_id(), instance=str(request.url.path)
        )
        return _problem_response(problem)

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, APIError):
            problem = exc.to_problem(request_id=_request_id(), instance=str(request.url.path))
            return _problem_response(problem)
        if isinstance(exc, RequestValidationError):
            return await validation_handler(request, exc)
        if isinstance(exc, StarletteHTTPException):
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        problem = internal_error().to_problem(
            request_id=_request_id(), instance=str(request.url.path)
        )
        return _problem_response(problem)

    def custom_openapi() -> dict:
        if app.openapi_schema is not None:
            return app.openapi_schema
        schema = _build_openapi(app)
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
    return app


def _request_id() -> str:
    return current_request_id() or "unknown"


def _problem_response(problem: ProblemDetail) -> JSONResponse:
    return JSONResponse(
        status_code=problem.status,
        content=jsonable_encoder(problem_json(problem)),
        media_type="application/problem+json",
    )


def _build_openapi(app: FastAPI) -> dict:
    from fastapi.openapi.utils import get_openapi

    schema = get_openapi(
        title=app.title,
        version=app.version,
        summary=app.summary,
        description=app.description,
        routes=app.routes,
    )
    schema["openapi"] = "3.1.0"
    schema["components"] = schema.get("components") or {}
    schema["components"]["securitySchemes"] = {
        "HTTPBearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "Clerk session token forwarded by the Next.js BFF. "
                "prem3-api verifies the session token. Tenant IDs are never "
                "accepted from the client."
            ),
        }
    }
    schema["components"]["schemas"] = schema.get("components", {}).get("schemas") or {}
    schema["components"]["schemas"]["ProblemDetail"] = ProblemDetail.model_json_schema()
    protected_prefixes = (
        "/v1/me",
        "/v1/workspaces",
        "/v1/billing/",
        "/v1/runs",
        "/v1/integrations",
    )
    for path, operations in schema.get("paths", {}).items():
        if path.startswith("/v1/integrations/google/oauth/callback"):
            continue
        if not path.startswith(protected_prefixes):
            continue
        if not isinstance(operations, dict):
            continue
        for operation in operations.values():
            if isinstance(operation, dict):
                operation.setdefault("security", [{"HTTPBearer": []}])
    return schema


def _default_upload_service(
    settings: Settings,
    repo: ControlPlaneRepository,
    *,
    signer: UploadSigner | None,
    object_store: ObjectStore | None,
) -> UploadService:
    if settings.raw_bucket:
        config = UploadConfig.from_settings(settings)
        resolved_signer: UploadSigner = signer or GcsV4UploadSigner()
        resolved_store: ObjectStore = object_store or GcsObjectStore()
    else:
        config = UploadConfig(
            raw_bucket="prem3-local-raw",
            signed_url_ttl_seconds=settings.upload_signed_url_ttl_seconds,
            max_files=settings.upload_max_files,
            max_file_bytes=settings.upload_max_file_bytes,
            max_total_bytes=settings.upload_max_total_bytes,
            runtime_sa=settings.runtime_sa,
        )
        # Cloud Run deploy must set MODELREADY_RAW_BUCKET (see runtime env file).
        # Factory tests may select cloud control-plane without a raw bucket; keep
        # fake signer/store so create_app remains import-safe.
        resolved_signer = signer or FakeUploadSigner()
        resolved_store = object_store or FakeObjectStore()
    return UploadService(
        repo=repo,
        config=config,
        signer=resolved_signer,
        object_store=resolved_store,
    )


def _default_google_services(
    settings: Settings,
    repo: ControlPlaneRepository,
    *,
    oauth_provider,
    vault,
    drive_client,
    bigquery_client,
    model_ready_resolver: ModelReadyEvidenceResolver | None = None,
) -> dict:
    oauth = oauth_provider
    if oauth is None and settings.google_oauth_client_id and settings.google_oauth_client_secret:
        oauth = RestGoogleOAuthProvider(
            client_id=settings.google_oauth_client_id,
            client_secret=settings.google_oauth_client_secret,
        )
    resolved_vault = vault
    live_google = bool(settings.google_oauth_client_id and settings.google_oauth_client_secret)
    if resolved_vault is None and live_google:
        if not settings.google_kms_key:
            raise RuntimeError(
                "Real Google OAuth requires GOOGLE_KMS_KEY for aes-256-gcm+kms-v1. "
                "InMemoryCredentialVault and hmac-sha256-xor-v1 are not production vaults."
            )
        resolved_vault = ControlPlaneCredentialVault(
            repo=repo,
            kms=CloudKmsKek(settings.google_kms_key),
        )
    if resolved_vault is None:
        resolved_vault = InMemoryCredentialVault()
    drive = drive_client or (RestDriveClient() if live_google else FakeDriveClient())
    bq = bigquery_client or (RestBigQueryClient() if live_google else FakeBigQueryClient())
    redirect_uri = settings.google_oauth_redirect_uri or (
        "http://localhost:8080/v1/integrations/google/oauth/callback"
    )
    frontend_origin = settings.prem3_frontend_origin or "http://localhost:3000"
    connections = GoogleConnectionService(
        repo=repo,
        vault=resolved_vault,
        oauth=oauth,
        redirect_uri=redirect_uri,
        frontend_origin=frontend_origin,
        ttl_seconds=settings.google_oauth_ttl_seconds,
    )
    drive_bindings = DriveBindingService(repo=repo, connections=connections, drive=drive)
    bq_bindings = BigQueryBindingService(repo=repo, connections=connections, bigquery=bq)
    return {
        "oauth": oauth,
        "vault": resolved_vault,
        "drive_client": drive,
        "bq_client": bq,
        "connections": connections,
        "drive": drive_bindings,
        "bigquery": bq_bindings,
        "import_governance": ImportGovernanceService(
            repo=repo, connections=connections, drive=drive, bigquery=bq
        ),
        "publish_governance": PublishGovernanceService(
            repo=repo, model_ready=model_ready_resolver
        ),
        "model_ready": model_ready_resolver or NullModelReadyEvidenceResolver(),
    }


def _default_evaluation_stack(
    settings: Settings,
    *,
    dispatcher: EvaluationDispatcher | None,
    launcher: EvaluationJobLauncher | None,
    verifier: ServiceIdentityVerifier | None,
) -> tuple[
    EvaluationDispatcher,
    EvaluationJobLauncher,
    ServiceIdentityVerifier | None,
    str,
]:
    job_name = settings.evaluation_worker_job or DEFAULT_EVALUATION_JOB_NAME
    if not uses_cloud_runtime():
        return (
            dispatcher or FakeEvaluationDispatcher(),
            launcher or FakeEvaluationJobLauncher(),
            verifier
            or FakeServiceIdentityVerifier(
                allowed_email=settings.evaluation_dispatcher_sa
                or "prem3-evaluation-dispatcher@local",
                audience=settings.evaluation_launch_audience
                or "http://localhost/internal/v1/evaluation-dispatches",
            ),
            job_name,
        )
    configured = bool(
        settings.evaluation_dispatch_queue
        and settings.evaluation_dispatcher_sa
        and settings.evaluation_launch_url
        and settings.evaluation_launch_audience
    )
    if not configured:
        return (
            dispatcher or UnavailableEvaluationDispatcher(),
            launcher or UnavailableEvaluationJobLauncher(),
            verifier,
            job_name,
        )
    return (
        dispatcher
        or CloudTasksEvaluationDispatcher(
            project_id=settings.project_id,
            location=settings.cloud_region,
            queue=settings.evaluation_dispatch_queue or "prem3-evaluation-dispatch",
            launch_url=settings.evaluation_launch_url or "",
            service_account_email=settings.evaluation_dispatcher_sa or "",
            audience=settings.evaluation_launch_audience or "",
        ),
        launcher
        or CloudRunEvaluationJobLauncher(
            project_id=settings.project_id,
            location=settings.cloud_region,
            job_name=job_name,
        ),
        verifier
        or GoogleOidcServiceIdentityVerifier(
            allowed_email=settings.evaluation_dispatcher_sa or "",
            audience=settings.evaluation_launch_audience or "",
        ),
        job_name,
    )


def _mmm_service_identity_verifier(settings: Settings):
    if not uses_cloud_runtime():
        return FakeServiceIdentityVerifier(
            allowed_email=settings.meridian_fit_dispatcher_sa
            or settings.evaluation_dispatcher_sa
            or "prem3-evaluation-dispatcher@local",
            audience=settings.meridian_fit_launch_audience
            or "http://localhost/internal/v1/mmm-fit-dispatches",
        )
    if not (
        settings.meridian_fit_dispatcher_sa and settings.meridian_fit_launch_audience
    ):
        return None
    return GoogleOidcServiceIdentityVerifier(
        allowed_email=settings.meridian_fit_dispatcher_sa,
        audience=settings.meridian_fit_launch_audience,
    )


def _default_mmm_stack(
    settings: Settings,
    control_plane: ControlPlaneRepository,
    *,
    modeling: MMMModelingService | None,
    launcher,
):
    if modeling is not None:
        return modeling, launcher or FakeEvaluationJobLauncher()
    if not uses_cloud_runtime():
        return MMMModelingService(), launcher or FakeEvaluationJobLauncher()
    client = getattr(control_plane, "client", None)
    repo = FirestoreModelingRepository(client) if client is not None else None
    configured = bool(
        settings.meridian_fit_dispatch_queue
        and settings.meridian_fit_dispatcher_sa
        and settings.meridian_fit_launch_url
        and settings.meridian_fit_launch_audience
    )
    dispatcher = None
    if configured:
        dispatcher = CloudTasksFitDispatcher(
            project_id=settings.project_id,
            location=settings.cloud_region,
            queue=settings.meridian_fit_dispatch_queue or "prem3-meridian-fit-dispatch",
            launch_url=settings.meridian_fit_launch_url or "",
            service_account_email=settings.meridian_fit_dispatcher_sa or "",
            audience=settings.meridian_fit_launch_audience or "",
        )
    service = MMMModelingService(
        repo,
        dispatcher=dispatcher,
        worker_image_digest=settings.meridian_model_worker_image,
        source_commit_sha=os.getenv("PREM3_SOURCE_COMMIT_SHA"),
        worker_build_id=os.getenv("PREM3_WORKER_BUILD_ID"),
        object_store=GcsObjectStore() if settings.artifact_bucket else None,
        artifact_bucket=settings.artifact_bucket,
    )
    if launcher is not None:
        return service, launcher
    if not configured:
        return service, UnavailableEvaluationJobLauncher()
    job_name = settings.meridian_model_worker_job or "prem3-meridian-model-worker"
    return service, CloudRunEvaluationJobLauncher(
        project_id=settings.project_id,
        location=settings.cloud_region,
        job_name=job_name,
        dispatch_env_var="PREM3_MMM_FIT_DISPATCH_ID",
    )


app = create_app()
