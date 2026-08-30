"""In-memory MTA store twin — compact metadata only."""

from __future__ import annotations

from threading import Lock

from app.modeling.mta.contracts import (
    MTAChannelGrouping,
    MTAInputContract,
    MTAProvisioningPlan,
    MTAProvisioningReceipt,
    MTAReadinessReceipt,
    MTATrackConfig,
)
from app.modeling.mta.runtime_contracts import (
    MTAExecutionDispatch,
    MTAExecutionPlan,
    MTARun,
    MTARunReceipt,
    MTAScheduledRefreshPlan,
)


class InMemoryMTARepository:
    def __init__(self) -> None:
        self._lock = Lock()
        self.configs: dict[str, MTATrackConfig] = {}
        self.contracts: dict[str, MTAInputContract] = {}
        self.readiness: dict[str, MTAReadinessReceipt] = {}
        self.groupings: dict[str, MTAChannelGrouping] = {}
        self.plans: dict[str, MTAProvisioningPlan] = {}
        self.receipts: dict[str, MTAProvisioningReceipt] = {}
        self.execution_plans: dict[str, MTAExecutionPlan] = {}
        self.dispatches: dict[str, MTAExecutionDispatch] = {}
        self.runs: dict[str, MTARun] = {}
        self.run_receipts: dict[str, MTARunReceipt] = {}
        self.scheduled_refresh: dict[str, MTAScheduledRefreshPlan] = {}
        self.latest_successful_run: dict[str, str] = {}
        self._canonical_dispatch: dict[str, str] = {}

    def put_config(self, *, track_id: str, config: MTATrackConfig) -> MTATrackConfig:
        with self._lock:
            self.configs[track_id] = config
            return config

    def get_config(self, track_id: str) -> MTATrackConfig | None:
        return self.configs.get(track_id)

    def put_contract(self, contract: MTAInputContract) -> MTAInputContract:
        with self._lock:
            self.contracts[contract.input_contract_id] = contract
            return contract

    def get_contract(self, input_contract_id: str) -> MTAInputContract | None:
        return self.contracts.get(input_contract_id)

    def put_readiness(self, receipt: MTAReadinessReceipt) -> MTAReadinessReceipt:
        with self._lock:
            self.readiness[receipt.track_id] = receipt
            return receipt

    def get_readiness(self, track_id: str) -> MTAReadinessReceipt | None:
        return self.readiness.get(track_id)

    def put_grouping(self, grouping: MTAChannelGrouping) -> MTAChannelGrouping:
        with self._lock:
            existing = self.groupings.get(grouping.version)
            if existing is not None and existing.fingerprint != grouping.fingerprint:
                raise ValueError(
                    f"Cannot mutate channel grouping version {grouping.version}."
                )
            self.groupings[grouping.version] = grouping
            return grouping

    def get_grouping(self, version: str) -> MTAChannelGrouping | None:
        return self.groupings.get(version)

    def put_plan(self, plan: MTAProvisioningPlan) -> MTAProvisioningPlan:
        with self._lock:
            self.plans[plan.plan_id] = plan
            return plan

    def put_provisioning_receipt(
        self, receipt: MTAProvisioningReceipt
    ) -> MTAProvisioningReceipt:
        with self._lock:
            self.receipts[receipt.receipt_id] = receipt
            return receipt

    def put_execution_plan(self, plan: MTAExecutionPlan) -> MTAExecutionPlan:
        with self._lock:
            existing = self.execution_plans.get(plan.execution_plan_id)
            if existing is not None and existing.fingerprint != plan.fingerprint:
                raise ValueError("Execution plan is immutable once stored.")
            self.execution_plans[plan.execution_plan_id] = plan
            return plan

    def get_execution_plan(self, execution_plan_id: str) -> MTAExecutionPlan | None:
        return self.execution_plans.get(execution_plan_id)

    def claim_canonical_dispatch(
        self, *, plan_fingerprint: str, dispatch: MTAExecutionDispatch
    ) -> MTAExecutionDispatch:
        with self._lock:
            existing_id = self._canonical_dispatch.get(plan_fingerprint)
            if existing_id is not None:
                return self.dispatches[existing_id]
            self.dispatches[dispatch.dispatch_id] = dispatch
            self._canonical_dispatch[plan_fingerprint] = dispatch.dispatch_id
            return dispatch

    def get_dispatch(self, dispatch_id: str) -> MTAExecutionDispatch | None:
        return self.dispatches.get(dispatch_id)

    def put_dispatch(self, dispatch: MTAExecutionDispatch) -> MTAExecutionDispatch:
        with self._lock:
            self.dispatches[dispatch.dispatch_id] = dispatch
            return dispatch

    def put_run(self, run: MTARun) -> MTARun:
        with self._lock:
            self.runs[run.run_id] = run
            return run

    def get_run(self, run_id: str) -> MTARun | None:
        return self.runs.get(run_id)

    def list_runs(self, *, project_id: str, cycle_id: str) -> list[MTARun]:
        return [
            r
            for r in self.runs.values()
            if r.project_id == project_id and r.cycle_id == cycle_id
        ]

    def put_run_receipt(self, receipt: MTARunReceipt) -> MTARunReceipt:
        with self._lock:
            self.run_receipts[receipt.receipt_id] = receipt
            return receipt

    def get_run_receipt_for_run(self, run_id: str) -> MTARunReceipt | None:
        for receipt in self.run_receipts.values():
            if receipt.run_id == run_id:
                return receipt
        return None

    def set_latest_successful_run(self, *, track_id: str, run_id: str) -> None:
        with self._lock:
            self.latest_successful_run[track_id] = run_id
