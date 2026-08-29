"""Compile verified MTA run outputs into an immutable MTAResultsSnapshot."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite
from typing import Any
from uuid import uuid4

from app.core.contracts import utc_now
from app.domain.channels import cached_channel_registry
from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mta import ADAPTER_VERSION
from app.modeling.mta.contracts import AttributionModelId
from app.modeling.mta.language import assert_result_payload_language
from app.modeling.mta.readback import InMemoryResultStore, ReadbackError
from app.modeling.mta.repository import InMemoryMTARepository
from app.modeling.mta.result_policies import (
    classify_channel_roles,
    classify_observability,
    classify_sensitivity,
    share_stats,
    unmapped_limitation,
)
from app.modeling.mta.results_contracts import (
    RESULTS_COMPILER_VERSION,
    ChannelRoleEvidence,
    ComparisonMetric,
    MarkovAttributionEvidence,
    MarkovChannelCredit,
    MarkovTransitionRow,
    MeasurementEvidenceAlignmentKey,
    MeasurementMethod,
    MetricAvailability,
    MetricAvailabilityItem,
    MTAChannelPositionEvidence,
    MTAChannelResult,
    MTAEvidenceAuthority,
    MTAJourneyPathEvidence,
    MTAJourneySummary,
    MTALimitation,
    MTALimitationType,
    MTAModelComparison,
    MTAModelComparisonCell,
    MTAModelSensitivityEvidence,
    MTAResultPointers,
    MTAResultsCompileError,
    MTAResultsCompileFailureClass,
    MTAResultSnapshotMetadata,
    MTAResultsSnapshot,
    MTAResultStatus,
    PathLengthBin,
    ShapleyAttributionEvidence,
    ShapleyChannelCredit,
    TimeToConversionBin,
)
from app.modeling.mta.runtime_contracts import MTARun, MTARunReceipt, MTARunStatus
from app.modeling.mta.visualizations import compile_visualizations

CREDIT_FIELDS: dict[str, tuple[str, str]] = {
    "FIRST_TOUCH": ("first_touch_credit", "first_touch_share"),
    "LAST_TOUCH": ("last_touch_credit", "last_touch_share"),
    "LAST_NON_DIRECT": ("last_non_direct_credit", "last_non_direct_share"),
    "LINEAR": ("linear_credit", "linear_share"),
    "TIME_DECAY": ("time_decay_credit", "time_decay_share"),
    "POSITION_BASED": ("position_based_credit", "position_based_share"),
    "MARKOV": ("markov_credit", "markov_share"),
    "SHAPLEY": ("shapley_credit", "shapley_share"),
}

TTC_BUCKETS: tuple[tuple[float, float | None], ...] = (
    (0.0, 1.0),
    (1.0, 3.0),
    (3.0, 7.0),
    (7.0, 14.0),
    (14.0, 30.0),
    (30.0, None),
)


def _finite(value: Any, *, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise MTAResultsCompileError(
            f"Invalid numeric {name}",
            failure_class=MTAResultsCompileFailureClass.MTA_RESULTS_INVALID_NUMERIC,
        ) from exc
    if not isfinite(number):
        raise MTAResultsCompileError(
            f"Non-finite numeric {name}",
            failure_class=MTAResultsCompileFailureClass.MTA_RESULTS_INVALID_NUMERIC,
        )
    return number


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _percentile(sorted_values: list[float], q: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    idx = min(len(sorted_values) - 1, max(0, int(round(q * (len(sorted_values) - 1)))))
    return float(sorted_values[idx])


def filter_model_comparison(
    comparison: MTAModelComparison, models: tuple[str, ...] | list[str] | None
) -> MTAModelComparison:
    """Presentation-only filter. Does not mutate the stored snapshot."""
    if not models:
        return comparison
    wanted = {str(m) for m in models}
    rows = tuple(row for row in comparison.rows if row.model_type in wanted)
    kept = tuple(m for m in comparison.models if m in wanted)
    return comparison.model_copy(update={"models": kept, "rows": rows})


@dataclass
class CompiledMTAResults:
    snapshot: MTAResultsSnapshot
    channel_results: tuple[MTAChannelResult, ...]
    comparison: MTAModelComparison
    sensitivity: tuple[MTAModelSensitivityEvidence, ...]
    markov: MarkovAttributionEvidence | None
    shapley: ShapleyAttributionEvidence
    journeys: MTAJourneySummary
    roles: tuple[ChannelRoleEvidence, ...]
    visualizations: tuple[Any, ...]
    summary_table_fingerprints: dict[str, str] = field(default_factory=dict)


class MTAResultsCompiler:
    def __init__(
        self,
        repo: InMemoryMTARepository,
        result_store: InMemoryResultStore,
        *,
        evidence_authority: MTAEvidenceAuthority = MTAEvidenceAuthority.TEST,
    ) -> None:
        self.repo = repo
        self.result_store = result_store
        self.evidence_authority = evidence_authority

    def compile(
        self,
        run_id: str,
        *,
        evidence_authority: MTAEvidenceAuthority | None = None,
        user_pseudo_id_coverage: float | None = None,
        traffic_source_coverage: float | None = None,
        channel_mapping_coverage: float | None = None,
        other_unclassified_share: float | None = None,
        conversion_value_coverage: float | None = None,
    ) -> CompiledMTAResults:
        run = self.repo.get_run(run_id)
        receipt = self.repo.get_run_receipt_for_run(run_id)
        if run is None or receipt is None:
            raise MTAResultsCompileError(
                "Verified MTARun receipt required",
                failure_class=MTAResultsCompileFailureClass.MTA_RESULTS_SOURCE_NOT_VERIFIED,
            )
        if run.status is not MTARunStatus.SUCCEEDED:
            raise MTAResultsCompileError(
                "MTARun is not SUCCEEDED",
                failure_class=MTAResultsCompileFailureClass.MTA_RESULTS_SOURCE_NOT_VERIFIED,
            )
        if receipt.readback_status != "VERIFIED":
            raise MTAResultsCompileError(
                "Run receipt read-back is not VERIFIED",
                failure_class=MTAResultsCompileFailureClass.MTA_RESULTS_SOURCE_NOT_VERIFIED,
            )
        try:
            compiled = self._compile_verified(
                run=run,
                receipt=receipt,
                evidence_authority=evidence_authority or self.evidence_authority,
                user_pseudo_id_coverage=user_pseudo_id_coverage,
                traffic_source_coverage=traffic_source_coverage,
                channel_mapping_coverage=channel_mapping_coverage,
                other_unclassified_share=other_unclassified_share,
                conversion_value_coverage=conversion_value_coverage,
            )
        except MTAResultsCompileError:
            raise
        except ReadbackError as exc:
            raise MTAResultsCompileError(
                str(exc),
                failure_class=MTAResultsCompileFailureClass.BIGQUERY_READBACK_ERROR,
            ) from exc
        except Exception as exc:
            raise MTAResultsCompileError(
                str(exc),
                failure_class=MTAResultsCompileFailureClass.UNKNOWN_ERROR,
            ) from exc
        # Failed compile must not mutate run status (we never write FAILED here).
        assert self.repo.get_run(run_id) is not None
        assert self.repo.get_run(run_id).status is MTARunStatus.SUCCEEDED
        return compiled

    def _compile_verified(
        self,
        *,
        run: MTARun,
        receipt: MTARunReceipt,
        evidence_authority: MTAEvidenceAuthority,
        user_pseudo_id_coverage: float | None,
        traffic_source_coverage: float | None,
        channel_mapping_coverage: float | None,
        other_unclassified_share: float | None,
        conversion_value_coverage: float | None,
    ) -> CompiledMTAResults:
        plan = self.repo.get_execution_plan(run.execution_plan_id)
        if plan is None:
            raise MTAResultsCompileError(
                "Execution plan missing",
                failure_class=MTAResultsCompileFailureClass.MTA_RESULTS_SOURCE_NOT_VERIFIED,
            )
        credit_table = f"mta_attribution_channel_results_{run.run_id}"
        try:
            credit_rows = self.result_store.read_back(credit_table)
        except ReadbackError as exc:
            raise MTAResultsCompileError(
                f"Missing required output {credit_table}",
                failure_class=MTAResultsCompileFailureClass.MTA_RESULTS_MISSING_REQUIRED_OUTPUT,
            ) from exc
        journeys = self._read_optional(f"_journeys_{run.run_id}")
        path_freqs = self._read_optional(f"mta_path_frequencies_{run.run_id}")
        registry = cached_channel_registry(1)
        registry_ids = set(registry.channel_ids())
        display = {c.channel_id: c.display_name for c in registry.channels}

        requested = tuple(m.value for m in plan.models)
        completed = tuple(e.model_type.value for e in run.model_evidence if e.status == "SUCCEEDED")
        shapley_status = self._shapley_availability(run=run, plan_models=requested)

        credits_by_model: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)
        all_channels: set[str] = set()
        for row in credit_rows:
            if "channel_id" not in row or "model_type" not in row:
                raise MTAResultsCompileError(
                    "Channel result row missing channel_id/model_type",
                    failure_class=MTAResultsCompileFailureClass.MTA_RESULTS_SCHEMA_ERROR,
                )
            channel_id = str(row["channel_id"])
            model_type = str(row["model_type"])
            credit = _finite(row.get("attributed_credit"), name="attributed_credit")
            share = _finite(row.get("attribution_share"), name="attribution_share")
            credits_by_model[model_type][channel_id] = {
                "attributed_credit": credit,
                "attribution_share": share,
            }
            all_channels.add(channel_id)

        journey_summary, position_by_channel = self._compile_journeys(
            run_id=run.run_id,
            journeys=journeys,
            path_freqs=path_freqs,
        )
        for channel_id in position_by_channel:
            all_channels.add(channel_id)

        markov = self._compile_markov(run, plan, credits_by_model.get("MARKOV", {}))
        shapley = self._compile_shapley(
            run,
            shapley_status=shapley_status,
            credits=credits_by_model.get("SHAPLEY", {}),
            path_count=len(journeys),
            distinct_channels=len(all_channels),
            plan=plan,
        )
        if markov and markov.availability is MetricAvailability.AVAILABLE:
            for channel_id, _effect in markov.removal_effects:
                all_channels.add(channel_id)

        observability = classify_observability(
            user_pseudo_id_coverage=user_pseudo_id_coverage
            if user_pseudo_id_coverage is not None
            else 1.0,
            traffic_source_coverage=traffic_source_coverage,
            channel_mapping_coverage=channel_mapping_coverage
            if channel_mapping_coverage is not None
            else (1.0 if all(ch in registry_ids for ch in all_channels) else 0.8),
            other_unclassified_share=other_unclassified_share,
            conversion_value_coverage=conversion_value_coverage,
            identity_strategy=plan and None,
            source_cutoff=receipt.completed_at.isoformat() if receipt.completed_at else None,
        )
        contract = self.repo.get_contract(plan.input_contract_id)
        if contract is not None:
            observability = observability.model_copy(
                update={"identity_strategy": contract.identity_strategy.value}
            )

        unknown = tuple(sorted(ch for ch in all_channels if ch not in registry_ids))
        limitations: list[MTALimitation] = []
        unmapped = unmapped_limitation(unknown)
        if unmapped:
            limitations.append(unmapped)
        if shapley.path_limit_applied:
            limitations.append(
                MTALimitation(
                    limitation_type=MTALimitationType.SHAPLEY_PATH_LIMIT,
                    statement=(
                        "SHAPLEY_PATH_LIMIT_APPLIED: longer paths were "
                        "truncated to pinned size."
                    ),
                )
            )

        comparison_rows: list[MTAModelComparisonCell] = []
        channel_results: list[MTAChannelResult] = []
        sensitivity_rows: list[MTAModelSensitivityEvidence] = []
        roles: list[ChannelRoleEvidence] = []
        model_params = {p.model_id.value: dict(p.parameters) for p in plan.model_parameters}

        snapshot_id = f"mrs_{uuid4().hex[:16]}"
        for channel_id in sorted(all_channels):
            pos = position_by_channel.get(channel_id)
            availability: list[MetricAvailabilityItem] = []
            fields: dict[str, Any] = {}
            available_shares: list[float] = []
            included_models: list[str] = []
            for model_id, (credit_f, share_f) in CREDIT_FIELDS.items():
                status = self._metric_status(
                    model_id=model_id,
                    requested=requested,
                    completed=completed,
                    shapley_status=shapley_status,
                    present=channel_id in credits_by_model.get(model_id, {}),
                )
                availability.append(MetricAvailabilityItem(metric_name=share_f, status=status))
                if status is MetricAvailability.AVAILABLE:
                    payload = credits_by_model[model_id][channel_id]
                    fields[credit_f] = payload["attributed_credit"]
                    fields[share_f] = payload["attribution_share"]
                    available_shares.append(payload["attribution_share"])
                    included_models.append(model_id)
                else:
                    fields[credit_f] = None
                    fields[share_f] = None
            stats = share_stats(available_shares)
            label = classify_sensitivity(stats["dispersion"])
            removal = None
            if markov and markov.availability is MetricAvailability.AVAILABLE:
                removal_map = dict(markov.removal_effects)
                removal = removal_map.get(channel_id)
                fields["markov_removal_effect"] = removal
            shapley_share = fields.get("shapley_share")
            first_share = pos.first_position_share if pos else 0.0
            middle_share = pos.middle_position_share if pos else 0.0
            last_share = pos.last_position_share if pos else 0.0
            presence_rate = pos.journey_presence_rate if pos else 0.0
            presence_count = pos.journey_presence_count if pos else 0
            role_labels = classify_channel_roles(
                channel_id=channel_id,
                first_share=first_share,
                middle_share=middle_share,
                last_share=last_share,
                journey_presence_rate=presence_rate,
                journey_presence_count=presence_count,
                sensitivity=label,
                observability=observability.status,
            )
            channel_limitations: list[MTALimitation] = []
            if channel_id not in registry_ids:
                channel_limitations.append(
                    MTALimitation(
                        limitation_type=MTALimitationType.UNMAPPED_TRAFFIC,
                        statement=f"{channel_id} is not in Channel Registry V1.",
                        affected_channels=(channel_id,),
                    )
                )
            alignment = MeasurementEvidenceAlignmentKey(
                channel_id=channel_id,
                conversion_event=contract.conversion_event if contract else "",
                period_start=contract.conversion_period_start if contract else "",
                period_end=contract.conversion_period_end if contract else "",
                method=MeasurementMethod.MTA,
                result_snapshot_id=snapshot_id,
            )
            result = MTAChannelResult(
                channel_id=channel_id,
                channel_display_name=display.get(channel_id, channel_id),
                touchpoint_count=None
                if pos is None
                else pos.first_position_count + pos.middle_position_count + pos.last_position_count,
                journey_count=presence_count,
                journey_presence_rate=None if pos is None else presence_rate,
                first_position_share=None if pos is None else first_share,
                middle_position_share=None if pos is None else middle_share,
                last_position_share=None if pos is None else last_share,
                model_credit_min=stats["min"],
                model_credit_max=stats["max"],
                model_credit_range=stats["range"],
                model_credit_dispersion=stats["dispersion"],
                model_sensitivity_label=label,
                role_profile=tuple(lab.value for lab in role_labels),
                metric_availability=tuple(availability),
                limitations=tuple(channel_limitations),
                evidence_refs=(credit_table, f"mta_channel_results_{snapshot_id}"),
                alignment_key=alignment,
                **fields,
            )
            channel_results.append(result)
            sensitivity_rows.append(
                MTAModelSensitivityEvidence(
                    channel_id=channel_id,
                    model_count=len(included_models),
                    min_attribution_share=stats["min"],
                    max_attribution_share=stats["max"],
                    range=stats["range"],
                    mean_attribution_share=stats["mean"],
                    median_attribution_share=stats["median"],
                    dispersion=stats["dispersion"],
                    sensitivity_label=label,
                    models_included=tuple(included_models),
                    is_confidence_interval=False,
                )
            )
            roles.append(
                ChannelRoleEvidence(
                    channel_id=channel_id,
                    labels=role_labels,
                    first_position_share=None if pos is None else first_share,
                    middle_position_share=None if pos is None else middle_share,
                    last_position_share=None if pos is None else last_share,
                    journey_presence_rate=None if pos is None else presence_rate,
                    markov_removal_effect=removal,
                    shapley_share=shapley_share,
                    sensitivity_label=label,
                    evidence_refs=(
                        credit_table,
                        f"mta_channel_position_evidence_{snapshot_id}",
                    ),
                )
            )
            for model_id in requested:
                payload = credits_by_model.get(model_id, {}).get(channel_id)
                status = self._metric_status(
                    model_id=model_id,
                    requested=requested,
                    completed=completed,
                    shapley_status=shapley_status,
                    present=payload is not None,
                )
                comparison_rows.append(
                    MTAModelComparisonCell(
                        channel_id=channel_id,
                        model_type=model_id,
                        attribution_share=(
                            None if payload is None else payload["attribution_share"]
                        ),
                        attributed_credit=(
                            None if payload is None else payload["attributed_credit"]
                        ),
                        availability=status,
                    )
                )

        comparison_payload = {
            "run": run.run_id,
            "rows": [r.model_dump() for r in comparison_rows],
        }
        comparison = MTAModelComparison(
            comparison_id=f"mcmp_{canonical_fingerprint(comparison_payload)[:16]}",
            run_id=run.run_id,
            models=tuple(completed),
            channels=tuple(sorted(all_channels)),
            comparison_metric=ComparisonMetric.ATTRIBUTION_SHARE,
            rows=tuple(comparison_rows),
            model_parameters=model_params,
            fingerprint=canonical_fingerprint(
                {"run": run.run_id, "rows": [r.model_dump() for r in comparison_rows]}
            ),
        )

        if any(
            s.sensitivity_label and s.sensitivity_label.value in {"HIGH", "VERY_HIGH"}
            for s in sensitivity_rows
        ):
            limitations.append(
                MTALimitation(
                    limitation_type=MTALimitationType.MODEL_SENSITIVITY,
                    statement="One or more channels show HIGH or VERY_HIGH cross-model dispersion.",
                )
            )

        status = MTAResultStatus.VERIFIED
        if shapley.availability is not MetricAvailability.AVAILABLE and "SHAPLEY" in requested:
            status = MTAResultStatus.PARTIAL
        if not journeys and not path_freqs:
            status = MTAResultStatus.REVIEW_REQUIRED

        grouping = self.repo.get_grouping(str(plan.channel_grouping_version))
        grouping_fp = grouping.fingerprint if grouping else plan.channel_grouping_fingerprint
        snapshot_payload = {
            "run_id": run.run_id,
            "receipt_fp": receipt.fingerprint,
            "plan_fp": plan.fingerprint,
            "compiler": RESULTS_COMPILER_VERSION,
            "registry_fp": registry.fingerprint,
            "grouping_fp": grouping_fp,
            "credits": canonical_fingerprint(credit_rows),
            "role_policy": roles[0].policy_version if roles else "mta_channel_role_policy_v1",
            "sensitivity_policy": "mta_sensitivity_policy_v1",
        }
        snapshot = MTAResultsSnapshot(
            result_snapshot_id=snapshot_id,
            project_id=run.project_id,
            cycle_id=run.cycle_id,
            track_id=run.track_id,
            run_id=run.run_id,
            execution_plan_id=run.execution_plan_id,
            run_receipt_id=receipt.receipt_id,
            result_status=status,
            evidence_authority=evidence_authority,
            computation_authority=receipt.computation_authority,
            conversion_event=contract.conversion_event if contract else "",
            conversion_period_start=contract.conversion_period_start if contract else "",
            conversion_period_end=contract.conversion_period_end if contract else "",
            lookback_window_days=contract.lookback_window_days if contract else 0,
            channel_registry_version=plan.channel_registry_version,
            channel_registry_fingerprint=registry.fingerprint,
            channel_grouping_version=str(plan.channel_grouping_version),
            channel_grouping_fingerprint=grouping_fp,
            identity_strategy=None if contract is None else contract.identity_strategy.value,
            sessionization_policy=None
            if contract is None
            else contract.sessionization_policy.value,
            traffic_source_policy=None
            if contract is None
            else contract.traffic_source_policy.value,
            direct_treatment_policy=None
            if contract is None
            else contract.direct_treatment_policy.value,
            models_requested=requested,
            models_completed=completed,
            channel_results_ref=f"mta_channel_results_{snapshot_id}",
            model_comparison_ref=f"mta_model_comparison_{snapshot_id}",
            markov_evidence_ref=None if markov is None else f"mta_markov_evidence_{snapshot_id}",
            shapley_evidence_ref=f"mta_shapley_evidence_{snapshot_id}",
            journey_summary_ref=f"mta_journey_summary_{snapshot_id}",
            observability_summary=observability,
            limitations=tuple(limitations),
            source_cutoff=receipt.completed_at.isoformat() if receipt.completed_at else None,
            source_manifest_ref=f"mta_run_manifest_{run.run_id}",
            runtime_versions={"dp6": plan.dp6_version, "adapter": plan.adapter_version},
            adapter_version=plan.adapter_version or ADAPTER_VERSION,
            run_receipt_fingerprint=receipt.fingerprint,
            execution_plan_fingerprint=plan.fingerprint,
            fingerprint=canonical_fingerprint(snapshot_payload),
        )
        visualizations = compile_visualizations(
            snapshot=snapshot,
            comparison=comparison,
            journeys=journey_summary,
            sensitivity=tuple(sensitivity_rows),
            markov=markov,
            shapley=shapley,
        )
        compiled = CompiledMTAResults(
            snapshot=snapshot,
            channel_results=tuple(channel_results),
            comparison=comparison,
            sensitivity=tuple(sensitivity_rows),
            markov=markov,
            shapley=shapley,
            journeys=journey_summary,
            roles=tuple(roles),
            visualizations=visualizations,
        )
        assert_result_payload_language(snapshot.model_dump(mode="json"))
        assert_result_payload_language([c.model_dump(mode="json") for c in channel_results])
        fingerprints = self._persist_summaries(compiled)
        compiled.summary_table_fingerprints = fingerprints
        self.repo.put_compiled_results(compiled)
        self._advance_pointers(compiled)
        return compiled

    def _read_optional(self, table: str) -> list[dict[str, Any]]:
        try:
            return self.result_store.read_back(table)
        except ReadbackError:
            return []

    def _shapley_availability(
        self, *, run: MTARun, plan_models: tuple[str, ...]
    ) -> MetricAvailability:
        if "SHAPLEY" not in plan_models:
            return MetricAvailability.NOT_APPLICABLE
        for evidence in run.model_evidence:
            if evidence.model_type is AttributionModelId.SHAPLEY and evidence.status == "SUCCEEDED":
                return MetricAvailability.AVAILABLE
        blob = " ".join(" ".join(e.limitations) for e in run.model_evidence).lower()
        if "preflight" in blob or "not_recommended" in blob or "review_required" in blob:
            return MetricAvailability.BLOCKED_BY_PREFLIGHT
        return MetricAvailability.NOT_RUN

    def _metric_status(
        self,
        *,
        model_id: str,
        requested: tuple[str, ...],
        completed: tuple[str, ...],
        shapley_status: MetricAvailability,
        present: bool,
    ) -> MetricAvailability:
        if model_id == "SHAPLEY" and shapley_status is not MetricAvailability.AVAILABLE:
            return shapley_status
        if model_id not in requested:
            return MetricAvailability.NOT_APPLICABLE
        if model_id not in completed:
            return MetricAvailability.NOT_RUN
        if not present:
            return MetricAvailability.NOT_RUN
        return MetricAvailability.AVAILABLE

    def _compile_markov(
        self,
        run: MTARun,
        plan: Any,
        markov_credits: dict[str, dict[str, float]],
    ) -> MarkovAttributionEvidence | None:
        if AttributionModelId.MARKOV not in plan.models:
            return MarkovAttributionEvidence(
                run_id=run.run_id,
                availability=MetricAvailability.NOT_APPLICABLE,
                unavailable_reason="Markov was not requested.",
                fingerprint=canonical_fingerprint({"run": run.run_id, "markov": "na"}),
            )
        transitions_table = f"mta_markov_transitions_{run.run_id}"
        effects_table = f"mta_markov_removal_effects_{run.run_id}"
        try:
            transition_rows = self.result_store.read_back(transitions_table)
            effect_rows = self.result_store.read_back(effects_table)
        except ReadbackError:
            return MarkovAttributionEvidence(
                run_id=run.run_id,
                availability=MetricAvailability.UNAVAILABLE_SOURCE,
                unavailable_reason="Markov output tables were not verified.",
                fingerprint=canonical_fingerprint({"run": run.run_id, "markov": "missing"}),
            )
        transitions = tuple(
            MarkovTransitionRow(
                from_channel_id=str(r["from_channel_id"]),
                to_channel_id=str(r["to_channel_id"]),
                transition_probability=_finite(
                    r["transition_probability"], name="transition_probability"
                ),
            )
            for r in transition_rows
        )
        effects = tuple(
            (
                str(r["channel_id"]),
                _finite(r["removal_effect"], name="removal_effect"),
            )
            for r in effect_rows
        )
        params = next(
            (
                p.parameters
                for p in plan.model_parameters
                if p.model_id is AttributionModelId.MARKOV
            ),
            {},
        )
        credits = tuple(
            MarkovChannelCredit(
                channel_id=ch,
                attributed_credit=vals["attributed_credit"],
                attribution_share=vals["attribution_share"],
                removal_effect=dict(effects).get(ch),
            )
            for ch, vals in sorted(markov_credits.items())
        )
        payload = {"transitions": [t.model_dump() for t in transitions], "effects": effects}
        return MarkovAttributionEvidence(
            run_id=run.run_id,
            channel_credit=credits,
            transition_matrix_ref=transitions_table,
            transitions=transitions,
            removal_effects=effects,
            transition_to_same_state=params.get("transition_to_same_state"),
            input_mode=plan.input_mode,
            conversion_value_as_frequency=params.get("conversion_value_as_frequency"),
            availability=MetricAvailability.AVAILABLE,
            fingerprint=canonical_fingerprint(payload),
        )

    def _compile_shapley(
        self,
        run: MTARun,
        *,
        shapley_status: MetricAvailability,
        credits: dict[str, dict[str, float]],
        path_count: int,
        distinct_channels: int,
        plan: Any,
    ) -> ShapleyAttributionEvidence:
        params = next(
            (
                p.parameters
                for p in plan.model_parameters
                if p.model_id is AttributionModelId.SHAPLEY
            ),
            {},
        )
        table = f"mta_shapley_results_{run.run_id}"
        rows = self._read_optional(table)
        path_limit = False
        size = params.get("size")
        order = params.get("order")
        values_col = params.get("values_col")
        if rows:
            path_limit = any(bool(r.get("path_limit_applied")) for r in rows)
            size = rows[0].get("size", size)
            order = rows[0].get("order_aware", order)
            values_col = rows[0].get("values_col", values_col)
        channel_credit = tuple(
            ShapleyChannelCredit(
                channel_id=ch,
                shapley_credit=vals["attributed_credit"],
                shapley_share=vals["attribution_share"],
            )
            for ch, vals in sorted(credits.items())
        )
        reason = None
        if shapley_status is MetricAvailability.BLOCKED_BY_PREFLIGHT:
            reason = "Shapley blocked by preflight; values were not fabricated."
        elif shapley_status is MetricAvailability.NOT_RUN:
            reason = "Shapley was not run."
        elif shapley_status is MetricAvailability.NOT_APPLICABLE:
            reason = "Shapley was not requested."
        payload = {
            "status": shapley_status.value,
            "credits": [c.model_dump() for c in channel_credit],
            "size": size,
            "path_limit": path_limit,
        }
        return ShapleyAttributionEvidence(
            run_id=run.run_id,
            channel_credit=channel_credit,
            size=None if size is None else int(size),
            order=None if order is None else bool(order),
            values_col=None if values_col is None else str(values_col),
            path_limit_applied=path_limit,
            preflight_status=shapley_status.value,
            input_path_count=path_count,
            distinct_channel_count=distinct_channels,
            availability=shapley_status,
            unavailable_reason=reason,
            fingerprint=canonical_fingerprint(payload),
        )

    def _compile_journeys(
        self,
        *,
        run_id: str,
        journeys: list[dict[str, Any]],
        path_freqs: list[dict[str, Any]],
    ) -> tuple[MTAJourneySummary, dict[str, MTAChannelPositionEvidence]]:
        converted = [j for j in journeys if j.get("converted", True)]
        nonconverted = [j for j in journeys if not j.get("converted", True)]
        len(converted) or 1
        lengths: list[float] = []
        ttc: list[float] = []
        first_counts: dict[str, int] = defaultdict(int)
        middle_counts: dict[str, int] = defaultdict(int)
        last_counts: dict[str, int] = defaultdict(int)
        presence: dict[str, int] = defaultdict(int)
        subjects: set[str] = set()
        identifier_keys = ("subject_key", "user_pseudo_id", "user_id", "ga_session_id")
        for journey in converted:
            channels = [str(c) for c in journey.get("channels") or []]
            if not channels and journey.get("path_string"):
                channels = [p.strip() for p in str(journey["path_string"]).split(">") if p.strip()]
            lengths.append(float(len(channels)))
            if "subject_key" in journey:
                subjects.add(str(journey["subject_key"]))
            times = journey.get("touchpoint_times") or journey.get("touchpoint_timestamps") or []
            start = _parse_ts(times[0] if times else None)
            end = _parse_ts(journey.get("conversion_ts"))
            if start is not None and end is not None:
                ttc.append(max(0.0, (end - start).total_seconds() / 86400.0))
            if not channels:
                continue
            first_counts[channels[0]] += 1
            last_counts[channels[-1]] += 1
            if len(channels) >= 3:
                for channel in channels[1:-1]:
                    middle_counts[channel] += 1
            for channel in set(channels):
                presence[channel] += 1
        converted_n = len(converted)
        denom = converted_n if converted_n else 1
        position: dict[str, MTAChannelPositionEvidence] = {}
        all_pos_channels = set(first_counts) | set(middle_counts) | set(last_counts) | set(presence)
        for channel_id in all_pos_channels:
            fc = first_counts[channel_id]
            mc = middle_counts[channel_id]
            lc = last_counts[channel_id]
            pc = presence[channel_id]
            position[channel_id] = MTAChannelPositionEvidence(
                channel_id=channel_id,
                first_position_count=fc,
                middle_position_count=mc,
                last_position_count=lc,
                first_position_share=fc / denom,
                middle_position_share=mc / denom,
                last_position_share=lc / denom,
                journey_presence_count=pc,
                journey_presence_rate=pc / denom,
            )
        length_hist: dict[int, int] = defaultdict(int)
        for length in lengths:
            length_hist[int(length)] += 1
        path_bins = tuple(
            PathLengthBin(
                touchpoint_count=k,
                journey_count=v,
                share=v / denom,
            )
            for k, v in sorted(length_hist.items())
        )
        ttc_counts = [0] * len(TTC_BUCKETS)
        for value in ttc:
            for i, (start, end) in enumerate(TTC_BUCKETS):
                if end is None:
                    if value >= start:
                        ttc_counts[i] += 1
                        break
                elif start <= value < end:
                    ttc_counts[i] += 1
                    break
        ttc_n = len(ttc) or 1
        ttc_bins = tuple(
            TimeToConversionBin(
                bucket_start=start,
                bucket_end=end,
                journey_count=ttc_counts[i],
                share=ttc_counts[i] / ttc_n,
            )
            for i, (start, end) in enumerate(TTC_BUCKETS)
        )
        freqs = path_freqs or []
        converting = [r for r in freqs if r.get("converted", True)]
        total_occ = sum(int(r.get("occurrences") or 0) for r in converting) or 1
        ranked = sorted(
            converting,
            key=lambda r: (-int(r.get("occurrences") or 0), str(r.get("path_string") or "")),
        )
        top: list[MTAJourneyPathEvidence] = []
        for i, row in enumerate(ranked[:20], start=1):
            path = str(row.get("path_string") or "")
            channels = tuple(p.strip() for p in path.split(">") if p.strip())
            leaked = [k for k in identifier_keys if k in row]
            if leaked:
                raise MTAResultsCompileError(
                    "Path summary must not expose user identifiers",
                    failure_class=MTAResultsCompileFailureClass.MTA_RESULTS_SCHEMA_ERROR,
                )
            top.append(
                MTAJourneyPathEvidence(
                    path_rank=i,
                    path_string=path,
                    channels=channels,
                    occurrences=int(row.get("occurrences") or 0),
                    conversion_count=int(row.get("occurrences") or 0),
                    conversion_value=float(row.get("conversion_value") or 0.0),
                    share_of_converting_paths=int(row.get("occurrences") or 0) / total_occ,
                )
            )
        sorted_len = sorted(lengths)
        sorted_ttc = sorted(ttc)
        single = sum(1 for length in lengths if length == 1)
        direct_share = presence.get("direct", 0) / denom if converted else None
        summary = MTAJourneySummary(
            journey_count=len(journeys),
            converted_journey_count=converted_n,
            nonconverting_journey_count=len(nonconverted),
            unique_subject_count=len(subjects) or None,
            avg_touchpoints=(sum(lengths) / len(lengths)) if lengths else None,
            median_touchpoints=_percentile(sorted_len, 0.5),
            p90_touchpoints=_percentile(sorted_len, 0.9),
            max_touchpoints=int(max(lengths)) if lengths else None,
            avg_time_to_conversion=(sum(ttc) / len(ttc)) if ttc else None,
            median_time_to_conversion=_percentile(sorted_ttc, 0.5),
            p90_time_to_conversion=_percentile(sorted_ttc, 0.9),
            single_touch_share=(single / denom) if converted else None,
            multi_touch_share=((converted_n - single) / denom) if converted else None,
            unique_path_count=len({r.get("path_string") for r in freqs})
            if freqs
            else len({j.get("path_string") for j in journeys}),
            direct_presence_share=direct_share,
            source_cutoff=None,
            top_paths=tuple(top),
            path_length_distribution=path_bins,
            time_to_conversion_distribution=ttc_bins,
            position_evidence=tuple(position[k] for k in sorted(position)),
        )
        del run_id
        return summary, position

    def _persist_summaries(self, compiled: CompiledMTAResults) -> dict[str, str]:
        snap = compiled.snapshot
        generated = utc_now().isoformat()
        tables: dict[str, list[dict[str, Any]]] = {
            f"mta_result_snapshots_{snap.result_snapshot_id}": [
                {
                    "result_snapshot_id": snap.result_snapshot_id,
                    "run_id": snap.run_id,
                    "execution_plan_id": snap.execution_plan_id,
                    "run_receipt_id": snap.run_receipt_id,
                    "result_status": snap.result_status.value,
                    "evidence_authority": snap.evidence_authority.value,
                    "fingerprint": snap.fingerprint,
                    "generated_at": generated,
                }
            ],
            snap.channel_results_ref: [
                {
                    "result_snapshot_id": snap.result_snapshot_id,
                    "run_id": snap.run_id,
                    "channel_id": row.channel_id,
                    "channel_display_name": row.channel_display_name,
                    "journey_presence_rate": row.journey_presence_rate,
                    "first_position_share": row.first_position_share,
                    "middle_position_share": row.middle_position_share,
                    "last_position_share": row.last_position_share,
                    "generated_at": generated,
                }
                for row in compiled.channel_results
            ],
            snap.model_comparison_ref: [
                {
                    "result_snapshot_id": snap.result_snapshot_id,
                    "run_id": snap.run_id,
                    "channel_id": cell.channel_id,
                    "model_type": cell.model_type,
                    "attribution_share": cell.attribution_share,
                    "attributed_credit": cell.attributed_credit,
                    "generated_at": generated,
                }
                for cell in compiled.comparison.rows
            ],
            f"mta_channel_position_evidence_{snap.result_snapshot_id}": [
                p.model_dump(mode="json") | {"result_snapshot_id": snap.result_snapshot_id}
                for p in compiled.journeys.position_evidence
            ],
            f"mta_model_sensitivity_{snap.result_snapshot_id}": [
                {
                    "result_snapshot_id": snap.result_snapshot_id,
                    "run_id": snap.run_id,
                    "channel_id": s.channel_id,
                    "dispersion": s.dispersion,
                    "sensitivity_label": None
                    if s.sensitivity_label is None
                    else s.sensitivity_label.value,
                    "policy_version": s.policy_version,
                    "is_confidence_interval": False,
                    "generated_at": generated,
                }
                for s in compiled.sensitivity
            ],
            f"mta_journey_path_summary_{snap.result_snapshot_id}": [
                {
                    "result_snapshot_id": snap.result_snapshot_id,
                    "run_id": snap.run_id,
                    "path_rank": p.path_rank,
                    "path_string": p.path_string,
                    "occurrences": p.occurrences,
                    "share_of_converting_paths": p.share_of_converting_paths,
                    "generated_at": generated,
                }
                for p in compiled.journeys.top_paths
            ],
            f"mta_path_length_distribution_{snap.result_snapshot_id}": [
                b.model_dump(mode="json") | {"result_snapshot_id": snap.result_snapshot_id}
                for b in compiled.journeys.path_length_distribution
            ],
            f"mta_time_to_conversion_distribution_{snap.result_snapshot_id}": [
                b.model_dump(mode="json") | {"result_snapshot_id": snap.result_snapshot_id}
                for b in compiled.journeys.time_to_conversion_distribution
            ],
            f"mta_channel_role_evidence_{snap.result_snapshot_id}": [
                {
                    "result_snapshot_id": snap.result_snapshot_id,
                    "run_id": snap.run_id,
                    "channel_id": r.channel_id,
                    "labels": [lab.value for lab in r.labels],
                    "policy_version": r.policy_version,
                    "generated_at": generated,
                }
                for r in compiled.roles
            ],
        }
        if compiled.markov is not None:
            tables[f"mta_markov_evidence_{snap.result_snapshot_id}"] = [
                compiled.markov.model_dump(mode="json")
            ]
        tables[f"mta_shapley_evidence_{snap.result_snapshot_id}"] = [
            compiled.shapley.model_dump(mode="json")
        ]
        tables[snap.journey_summary_ref] = [compiled.journeys.model_dump(mode="json")]
        fingerprints: dict[str, str] = {}
        for table, rows in tables.items():
            fingerprints[table] = self.result_store.write(table, rows)
        self.result_store.verify_required(
            run_id=snap.result_snapshot_id, required_tables=list(tables)
        )
        return fingerprints

    def _advance_pointers(self, compiled: CompiledMTAResults) -> None:
        snap = compiled.snapshot
        existing = self.repo.get_result_pointers(snap.track_id)
        current = None if existing is None else existing.current_result_snapshot_id
        explicit = False if existing is None else existing.current_explicit
        if current is None and snap.result_status is MTAResultStatus.VERIFIED:
            current = snap.result_snapshot_id
        pointers = MTAResultPointers(
            track_id=snap.track_id,
            latest_result_snapshot_id=snap.result_snapshot_id,
            current_result_snapshot_id=current,
            current_explicit=explicit,
        )
        self.repo.put_result_pointers(pointers)
        self.repo.put_snapshot_metadata(
            MTAResultSnapshotMetadata(
                result_snapshot_id=snap.result_snapshot_id,
                project_id=snap.project_id,
                cycle_id=snap.cycle_id,
                track_id=snap.track_id,
                run_id=snap.run_id,
                result_status=snap.result_status,
                evidence_authority=snap.evidence_authority,
                fingerprint=snap.fingerprint,
                models_completed=snap.models_completed,
                observability_status=snap.observability_summary.status,
                generated_at=snap.generated_at,
            )
        )
