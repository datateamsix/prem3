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


class InMemoryMTARepository:
    def __init__(self) -> None:
        self._lock = Lock()
        self.configs: dict[str, MTATrackConfig] = {}
        self.contracts: dict[str, MTAInputContract] = {}
        self.readiness: dict[str, MTAReadinessReceipt] = {}
        self.groupings: dict[str, MTAChannelGrouping] = {}
        self.plans: dict[str, MTAProvisioningPlan] = {}
        self.receipts: dict[str, MTAProvisioningReceipt] = {}

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
