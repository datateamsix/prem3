"""Thin MTA domain service — readiness, provision, refresh, runs, dispatch."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.core.contracts import utc_now
from app.modeling.mta.adapters.dp6_mam_v1_0_11 import DP6MAMAdapter
from app.modeling.mta.channel_grouping import build_channel_grouping
from app.modeling.mta.contracts import (
    AttributionModelId,
    MTAChannelGrouping,
    MTAChannelGroupingRule,
    MTAInputContract,
    MTAOverviewReadModel,
    MTAProvisioningPlan,
    MTAProvisioningReceipt,
    MTAReadinessReceipt,
    MTAReadinessState,
    MTATrackConfig,
)
from app.modeling.mta.dispatch import FakeMTADispatcher, MTADispatcher
from app.modeling.mta.execution import build_analysis_config, compile_execution_plan
from app.modeling.mta.ga4_discovery import TableLister, discover_ga4_exports
from app.modeling.mta.input_contract import build_input_contract
from app.modeling.mta.journeys import (
    assert_touchpoint_order,
    deterministic_journey_id,
    path_string,
    reduce_path_frequencies,
)
from app.modeling.mta.overview import assemble_mta_overview
from app.modeling.mta.provisioning import (
    compile_mta_provisioning_plan,
    execute_mta_provisioning_plan_fake,
)
from app.modeling.mta.readback import InMemoryResultStore
from app.modeling.mta.readiness import evaluate_mta_readiness
from app.modeling.mta.receipt import build_run_receipt
from app.modeling.mta.repository import InMemoryMTARepository
from app.modeling.mta.runtime_contracts import (
    MTADispatchStatus,
    MTAExecutionDispatch,
    MTAModelExecutionEvidence,
    MTARun,
    MTARunReceipt,
    MTARunStatus,
)
from app.modeling.mta.shapley_preflight import run_shapley_preflight
from app.modeling.mta.states import MTATrackStage


class MTAService:
    def __init__(
        self,
        repo: InMemoryMTARepository | None = None,
        *,
        dispatcher: MTADispatcher | None = None,
        result_store: InMemoryResultStore | None = None,
        dp6: DP6MAMAdapter | None = None,
    ) -> None:
        self.repo = repo or InMemoryMTARepository()
        self.dispatcher = dispatcher or FakeMTADispatcher()
        self.result_store = result_store or InMemoryResultStore()
        self.dp6 = dp6 or DP6MAMAdapter(fake=True)

    def upsert_config(self, *, track_id: str, config: MTATrackConfig) -> MTATrackConfig:
        return self.repo.put_config(track_id=track_id, config=config)

    def get_config(self, track_id: str) -> MTATrackConfig | None:
        return self.repo.get_config(track_id)

    def discover_ga4(self, catalog: TableLister, *, gcp_project_id: str):
        return discover_ga4_exports(catalog, gcp_project_id=gcp_project_id)

    def save_grouping(
        self,
        *,
        version: str,
        rules: tuple[MTAChannelGroupingRule, ...] | list[MTAChannelGroupingRule],
        created_by: str,
        approved_by: str | None = None,
        business_profile_snapshot_id: str | None = None,
    ) -> MTAChannelGrouping:
        grouping = build_channel_grouping(
            version=version,
            rules=rules,
            created_by=created_by,
            approved_by=approved_by,
            business_profile_snapshot_id=business_profile_snapshot_id,
        )
        return self.repo.put_grouping(grouping)

    def create_input_contract(self, **kwargs) -> MTAInputContract:
        contract = build_input_contract(**kwargs)
        return self.repo.put_contract(contract)

    def evaluate_readiness(
        self,
        *,
        tenant_id: str,
        project_id: str,
        cycle_id: str,
        track_id: str,
        contract: MTAInputContract | None,
        **kwargs,
    ) -> MTAReadinessReceipt:
        receipt = evaluate_mta_readiness(
            tenant_id=tenant_id,
            project_id=project_id,
            cycle_id=cycle_id,
            track_id=track_id,
            contract=contract,
            **kwargs,
        )
        return self.repo.put_readiness(receipt)

    def compile_provisioning_plan(
        self,
        *,
        plan_id: str,
        tenant_id: str,
        project_id: str,
        cycle_id: str,
        track_id: str,
        gcp_project_id: str,
        channel_grouping_version: str,
        models: tuple[AttributionModelId, ...] = (),
    ) -> MTAProvisioningPlan:
        plan = compile_mta_provisioning_plan(
            plan_id=plan_id,
            tenant_id=tenant_id,
            project_id=project_id,
            cycle_id=cycle_id,
            track_id=track_id,
            gcp_project_id=gcp_project_id,
            channel_grouping_version=channel_grouping_version,
            models=models,
        )
        return self.repo.put_plan(plan)

    def execute_provisioning_fake(
        self, plan: MTAProvisioningPlan, *, existing: set[str] | None = None
    ) -> MTAProvisioningReceipt:
        receipt = execute_mta_provisioning_plan_fake(plan, existing_assets=existing)
        return self.repo.put_provisioning_receipt(receipt)

    def overview(
        self,
        *,
        project_id: str,
        cycle_id: str,
        track_id: str | None,
        foundation_ready: bool,
        track_id_for_config: str | None = None,
    ) -> MTAOverviewReadModel:
        tid = track_id_for_config or track_id or ""
        config = self.repo.get_config(tid) if tid else None
        readiness = self.repo.get_readiness(tid) if tid else None
        contract = None
        if readiness and readiness.input_contract_fingerprint:
            for item in self.repo.contracts.values():
                if item.fingerprint == readiness.input_contract_fingerprint:
                    contract = item
                    break
        model = assemble_mta_overview(
            project_id=project_id,
            cycle_id=cycle_id,
            track_id=track_id,
            foundation_ready=foundation_ready,
            config=config,
            readiness=readiness,
            contract=contract,
        )
        latest = self.repo.latest_successful_run.get(tid)
        if latest:
            run = self.repo.get_run(latest)
            if run and run.status is MTARunStatus.SUCCEEDED:
                model = model.model_copy(
                    update={
                        "latest_result_state": "RESULTS_READY",
                        "attribution_models": tuple(m.value for m in run.model_evidence),
                    }
                )
        return model

    def mark_configuring(self, track_id: str) -> MTATrackConfig:
        config = self.repo.get_config(track_id) or MTATrackConfig()
        updated = config.model_copy(
            update={"domain_stage": MTATrackStage.CONFIGURING}
        )
        return self.repo.put_config(track_id=track_id, config=updated)

    def start_run(
        self,
        *,
        tenant_id: str,
        project_id: str,
        cycle_id: str,
        track_id: str,
        channel_registry_version: int = 1,
        channel_grouping_version: int = 1,
        channel_grouping_fingerprint: str = "grouping_fp",
        journeys: list[dict[str, Any]] | None = None,
        worker_image_digest: str | None = None,
        source_commit_sha: str | None = None,
        # Authority reject surface — must be None from callers
        gcp_project_override: str | None = None,
        bq_destination_override: str | None = None,
        channel_grouping_routine_override: str | None = None,
        worker_image_override: str | None = None,
    ) -> MTARun:
        if any(
            [
                gcp_project_override,
                bq_destination_override,
                channel_grouping_routine_override,
                worker_image_override,
            ]
        ):
            raise PermissionError("Caller cannot override MTA execution authority.")

        readiness = self.repo.get_readiness(track_id)
        if readiness is None or readiness.state is not MTAReadinessState.MTA_INPUT_READY:
            raise PermissionError("MTA_INPUT_READY receipt required before execution.")

        contract = None
        for item in self.repo.contracts.values():
            if item.fingerprint == readiness.input_contract_fingerprint:
                contract = item
                break
        if contract is None:
            raise ValueError("Input contract for readiness receipt not found.")

        analysis = build_analysis_config(
            contract,
            channel_registry_version=channel_registry_version,
            channel_grouping_version=channel_grouping_version,
        )
        preflight = None
        if AttributionModelId.SHAPLEY in analysis.models:
            preflight = run_shapley_preflight(
                distinct_channel_count=8,
                max_path_length=6,
                configured_size=4,
                order_aware=True,
            )

        journey_rows = journeys or []
        for row in journey_rows:
            assert_touchpoint_order(
                row.get("touchpoint_times", []),
                conversion_ts=row.get("conversion_ts"),
            )
            if "journey_id" not in row:
                row["journey_id"] = deterministic_journey_id(
                    subject_key=row["subject_key"],
                    conversion_event=row.get("conversion_event", contract.conversion_event),
                    conversion_ts=row.get("conversion_ts"),
                    channels=row.get("channels", []),
                    touchpoint_times=row.get("touchpoint_times", []),
                )
            row["path_string"] = row.get("path_string") or path_string(row.get("channels", []))

        journey_fp = analysis.fingerprint
        plan = compile_execution_plan(
            execution_plan_id=f"mtex_{uuid4().hex[:16]}",
            tenant_id=tenant_id,
            project_id=project_id,
            cycle_id=cycle_id,
            track_id=track_id,
            contract=contract,
            readiness_receipt_id=readiness.receipt_id,
            analysis=analysis,
            channel_grouping_fingerprint=channel_grouping_fingerprint,
            journey_fingerprint=journey_fp,
            shapley_preflight=preflight,
            worker_image_digest=worker_image_digest,
            source_commit_sha=source_commit_sha,
        )
        self.repo.put_execution_plan(plan)

        run = MTARun(
            run_id=f"mtrun_{uuid4().hex[:16]}",
            tenant_id=tenant_id,
            project_id=project_id,
            cycle_id=cycle_id,
            track_id=track_id,
            execution_plan_id=plan.execution_plan_id,
            execution_plan_fingerprint=plan.fingerprint,
            status=MTARunStatus.QUEUED,
            worker_image_digest=worker_image_digest,
            source_commit_sha=source_commit_sha,
            started_at=utc_now(),
        )
        self.repo.put_run(run)

        dispatch = MTAExecutionDispatch(
            dispatch_id=f"mtdsp_{uuid4().hex[:16]}",
            tenant_id=tenant_id,
            project_id=project_id,
            cycle_id=cycle_id,
            track_id=track_id,
            run_id=run.run_id,
            execution_plan_id=plan.execution_plan_id,
            execution_plan_fingerprint=plan.fingerprint,
            status=MTADispatchStatus.PENDING,
        )
        dispatch = self.repo.claim_canonical_dispatch(
            plan_fingerprint=plan.fingerprint, dispatch=dispatch
        )
        task_name = self.dispatcher.enqueue(dispatch)
        dispatch = dispatch.model_copy(
            update={
                "status": MTADispatchStatus.QUEUED,
                "cloud_task_name": task_name,
                "updated_at": utc_now(),
            }
        )
        self.repo.put_dispatch(dispatch)
        run = run.model_copy(update={"dispatch_id": dispatch.dispatch_id})
        self.repo.put_run(run)
        # Stash journeys on run for fake worker via result store side channel
        self.result_store.write(f"_journeys_{run.run_id}", journey_rows)
        return run

    def launch_dispatch(self, *, dispatch_id: str) -> MTAExecutionDispatch:
        dispatch = self.repo.get_dispatch(dispatch_id)
        if dispatch is None:
            raise KeyError(f"Unknown dispatch {dispatch_id}")
        if dispatch.cloud_run_execution_name:
            return dispatch
        execution_name = f"prem3-mta-worker/{dispatch_id}"
        updated = dispatch.model_copy(
            update={
                "status": MTADispatchStatus.LAUNCHED,
                "cloud_run_execution_name": execution_name,
                "updated_at": utc_now(),
            }
        )
        return self.repo.put_dispatch(updated)

    def execute_fit_dispatch(self, *, dispatch_id: str) -> MTARunReceipt:
        """Worker entry — restore authority from dispatch_id only."""
        dispatch = self.repo.get_dispatch(dispatch_id)
        if dispatch is None:
            raise KeyError(dispatch_id)
        plan = self.repo.get_execution_plan(dispatch.execution_plan_id)
        if plan is None:
            raise KeyError(dispatch.execution_plan_id)
        if plan.fingerprint != dispatch.execution_plan_fingerprint:
            raise PermissionError("Execution plan fingerprint mismatch.")
        run = self.repo.get_run(dispatch.run_id)
        if run is None:
            raise KeyError(dispatch.run_id)
        if run.status in (MTARunStatus.SUCCEEDED, MTARunStatus.FAILED):
            receipt = self.repo.get_run_receipt_for_run(run.run_id)
            if receipt:
                return receipt

        run = run.model_copy(update={"status": MTARunStatus.RUNNING})
        self.repo.put_run(run)

        journeys = self.result_store.read_back(f"_journeys_{run.run_id}")
        paths = [list(j.get("channels", [])) for j in journeys if j.get("converted", True)]
        if not paths:
            paths = [["search_paid", "social_paid", "direct"]]
        conversions = [float(j.get("conversion_value") or 1.0) for j in journeys] or [1.0]
        freqs = reduce_path_frequencies(
            [
                {
                    **j,
                    "path_string": j.get("path_string")
                    or path_string(j.get("channels", [])),
                    "converted": bool(j.get("converted", True)),
                }
                for j in (
                    journeys
                    or [
                        {
                            "path_string": "search_paid > social_paid > direct",
                            "converted": True,
                            "conversion_value": 1.0,
                            "channels": ["search_paid", "social_paid", "direct"],
                        }
                    ]
                )
            ]
        )

        evidence: list[MTAModelExecutionEvidence] = []
        channel_rows: list[dict[str, Any]] = []
        for param_set in plan.model_parameters:
            started = utc_now()
            result = self.dp6.run_model(
                param_set.model_id,
                paths=paths,
                conversions=conversions[: len(paths)],
                parameters=param_set.parameters,
                input_mode=plan.input_mode,
            )
            for credit in result.credits:
                channel_rows.append(
                    {
                        "run_id": run.run_id,
                        "model_type": param_set.model_id.value,
                        "channel_id": credit.channel_id,
                        "channel_name": credit.channel_id,
                        "attributed_credit": credit.attributed_credit,
                        "attribution_share": credit.attribution_share,
                    }
                )
            evidence.append(
                MTAModelExecutionEvidence(
                    model_type=param_set.model_id,
                    status="SUCCEEDED",
                    parameters=param_set.parameters,
                    input_mode=plan.input_mode,
                    started_at=started,
                    completed_at=utc_now(),
                    runtime_version=self.dp6.version,
                    row_count=len(result.credits),
                    path_count=len(paths),
                    limitations=tuple(result.limitations),
                )
            )
            if result.markov:
                self.result_store.write(
                    f"mta_markov_transitions_{run.run_id}",
                    [
                        {
                            "from_channel_id": a,
                            "to_channel_id": b,
                            "transition_probability": p,
                        }
                        for a, b, p in result.markov.transitions
                    ],
                )
                self.result_store.write(
                    f"mta_markov_removal_effects_{run.run_id}",
                    [
                        {"channel_id": ch, "removal_effect": effect}
                        for ch, effect in result.markov.removal_effects
                    ],
                )
            if result.shapley:
                self.result_store.write(
                    f"mta_shapley_results_{run.run_id}",
                    [
                        {
                            "channel_id": c.channel_id,
                            "shapley_credit": c.attributed_credit,
                            "shapley_share": c.attribution_share,
                            "size": result.shapley.size,
                            "order_aware": result.shapley.order_aware,
                            "values_col": result.shapley.values_col,
                            "path_limit_applied": result.shapley.path_limit_applied,
                        }
                        for c in result.shapley.credits
                    ],
                )

        self.result_store.write(
            f"mta_attribution_channel_results_{run.run_id}", channel_rows
        )
        self.result_store.write(
            f"mta_path_frequencies_{run.run_id}", freqs
        )
        self.result_store.write(
            f"mta_run_manifest_{run.run_id}",
            [
                {
                    "run_id": run.run_id,
                    "execution_plan_id": plan.execution_plan_id,
                    "dp6_version": plan.dp6_version,
                    "adapter_version": plan.adapter_version,
                    "models": [m.value for m in plan.models],
                    "input_mode": plan.input_mode.value,
                }
            ],
        )

        required = [
            f"mta_attribution_channel_results_{run.run_id}",
            f"mta_run_manifest_{run.run_id}",
        ]
        if AttributionModelId.MARKOV in plan.models:
            required.extend(
                [
                    f"mta_markov_transitions_{run.run_id}",
                    f"mta_markov_removal_effects_{run.run_id}",
                ]
            )
        self.result_store.verify_required(run_id=run.run_id, required_tables=required)

        run = run.model_copy(
            update={
                "status": MTARunStatus.SUCCEEDED,
                "model_evidence": tuple(evidence),
                "completed_at": utc_now(),
            }
        )
        self.repo.put_run(run)
        self.result_store.advance_current(
            run_id=run.run_id,
            mapping={
                "mta_attribution_channels_current": (
                    f"mta_attribution_channel_results_{run.run_id}"
                )
            },
            run_status=run.status,
        )
        self.repo.set_latest_successful_run(track_id=run.track_id, run_id=run.run_id)
        contract = self.repo.get_contract(plan.input_contract_id)
        receipt = build_run_receipt(
            run,
            input_contract_fingerprint=contract.fingerprint if contract else "",
            session_count=0,
            touchpoint_count=0,
            journey_count=len(journeys),
            grouped_path_count=len(freqs),
            output_refs=required,
            readback_status="VERIFIED",
        )
        self.repo.put_run_receipt(receipt)
        self.repo.put_dispatch(
            dispatch.model_copy(
                update={"status": MTADispatchStatus.COMPLETE, "updated_at": utc_now()}
            )
        )
        return receipt
