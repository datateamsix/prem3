"""MTA BigQuery provisioning plan compiler — inventory + fingerprints (DDL in M5-01)."""

from __future__ import annotations

from app.modeling.common.fingerprints import canonical_fingerprint
from app.modeling.mta.contracts import (
    AttributionModelId,
    MTAProvisionedAsset,
    MTAProvisioningPlan,
    MTAProvisioningReceipt,
)


def mta_asset_inventory(
    *,
    run_id: str,
    models: tuple[AttributionModelId, ...] | list[AttributionModelId],
) -> tuple[MTAProvisionedAsset, ...]:
    model_set = set(models)
    assets: list[MTAProvisionedAsset] = [
        MTAProvisionedAsset(
            asset_name="channel_grouping_v1",
            asset_kind="ROUTINE",
            description="Versioned channel grouping UDF (pin exact version on runs)",
        ),
        MTAProvisionedAsset(
            asset_name=f"mta_source_manifest_{run_id}",
            asset_kind="TABLE",
        ),
        MTAProvisionedAsset(
            asset_name=f"mta_session_touchpoints_{run_id}",
            asset_kind="TABLE",
        ),
        MTAProvisionedAsset(
            asset_name=f"mta_journeys_{run_id}",
            asset_kind="TABLE",
        ),
        MTAProvisionedAsset(
            asset_name=f"mta_path_frequencies_{run_id}",
            asset_kind="TABLE",
        ),
        MTAProvisionedAsset(
            asset_name=f"mta_attribution_journey_results_{run_id}",
            asset_kind="TABLE",
        ),
        MTAProvisionedAsset(
            asset_name=f"mta_attribution_channel_results_{run_id}",
            asset_kind="TABLE",
        ),
        MTAProvisionedAsset(
            asset_name=f"mta_model_comparison_{run_id}",
            asset_kind="TABLE",
        ),
        MTAProvisionedAsset(
            asset_name=f"mta_run_manifest_{run_id}",
            asset_kind="TABLE",
        ),
        MTAProvisionedAsset(
            asset_name=f"mta_markov_transitions_{run_id}",
            asset_kind="TABLE",
            enabled=AttributionModelId.MARKOV in model_set,
            required_models=(AttributionModelId.MARKOV,),
        ),
        MTAProvisionedAsset(
            asset_name=f"mta_markov_removal_effects_{run_id}",
            asset_kind="TABLE",
            enabled=AttributionModelId.MARKOV in model_set,
            required_models=(AttributionModelId.MARKOV,),
        ),
        MTAProvisionedAsset(
            asset_name=f"mta_shapley_results_{run_id}",
            asset_kind="TABLE",
            enabled=AttributionModelId.SHAPLEY in model_set,
            required_models=(AttributionModelId.SHAPLEY,),
        ),
    ]
    return tuple(assets)


STABLE_CURRENT_VIEWS = (
    "mta_session_touchpoints_current",
    "mta_journeys_current",
    "mta_attribution_channels_current",
    "mta_model_comparison_current",
)


def compile_mta_provisioning_plan(
    *,
    plan_id: str,
    tenant_id: str,
    project_id: str,
    cycle_id: str,
    track_id: str,
    gcp_project_id: str,
    channel_grouping_version: str,
    run_id: str = "plan",
    models: tuple[AttributionModelId, ...] | list[AttributionModelId] = (),
    dataset_id: str = "prem3_modeling",
) -> MTAProvisioningPlan:
    assets = mta_asset_inventory(run_id=run_id, models=models)
    routine = f"channel_grouping_{channel_grouping_version}"
    payload = {
        "gcp_project_id": gcp_project_id,
        "dataset_id": dataset_id,
        "routine": routine,
        "assets": [a.model_dump(mode="json") for a in assets if a.enabled],
        "views": list(STABLE_CURRENT_VIEWS),
    }
    return MTAProvisioningPlan(
        plan_id=plan_id,
        tenant_id=tenant_id,
        project_id=project_id,
        cycle_id=cycle_id,
        track_id=track_id,
        gcp_project_id=gcp_project_id,
        dataset_id=dataset_id,
        channel_grouping_version=channel_grouping_version,
        assets=assets,
        channel_grouping_routine=routine,
        fingerprint=canonical_fingerprint(payload),
    )


def execute_mta_provisioning_plan_fake(
    plan: MTAProvisioningPlan,
    *,
    existing_assets: set[str] | None = None,
) -> MTAProvisioningReceipt:
    """Idempotent fake executor for unit tests — no live BigQuery DDL in M5-00."""
    existing = existing_assets or set()
    created: list[str] = []
    reused: list[str] = []
    for asset in plan.assets:
        if not asset.enabled:
            continue
        name = f"{plan.dataset_id}.{asset.asset_name}"
        if name in existing or asset.asset_name in existing:
            reused.append(asset.asset_name)
        else:
            created.append(asset.asset_name)
            existing.add(asset.asset_name)
    if plan.channel_grouping_routine not in existing:
        created.append(plan.channel_grouping_routine)
    else:
        reused.append(plan.channel_grouping_routine)
    return MTAProvisioningReceipt(
        receipt_id=f"mta_prov_{plan.fingerprint[:16]}",
        plan_id=plan.plan_id,
        plan_fingerprint=plan.fingerprint,
        tenant_id=plan.tenant_id,
        project_id=plan.project_id,
        created=tuple(created),
        reused=tuple(reused),
        untouched=(),
        verified=True,
    )
