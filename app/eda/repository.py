"""Durable extended EDA report metadata. Official HTML stays in object storage."""

from __future__ import annotations

from threading import Lock
from typing import Any, Protocol

from app.control_plane.serialization import document_to_model, model_to_document
from app.eda.extended_contracts import PreM3ExtendedEDAReport
from app.modeling.common.errors import ModelVersionImmutableError

COL_TENANTS = "tenants"
COL_WORKSPACES = "workspaces"
COL_REPORTS = "extended_eda_reports"
COL_INDEX = "extended_eda_index"


class ExtendedEDARepository(Protocol):
    def put_report(self, report: PreM3ExtendedEDAReport) -> PreM3ExtendedEDAReport: ...

    def get_report(
        self, *, tenant_id: str, project_id: str, report_id: str
    ) -> PreM3ExtendedEDAReport | None: ...

    def latest_for_cycle(
        self, *, tenant_id: str, project_id: str, cycle_id: str
    ) -> PreM3ExtendedEDAReport | None: ...

    def list_for_cycle(
        self, *, tenant_id: str, project_id: str, cycle_id: str
    ) -> list[PreM3ExtendedEDAReport]: ...

    def get_by_fingerprint(
        self, *, tenant_id: str, project_id: str, cycle_id: str, fingerprint: str
    ) -> PreM3ExtendedEDAReport | None: ...


class InMemoryExtendedEDARepository:
    def __init__(self) -> None:
        self._lock = Lock()
        self.reports: dict[str, PreM3ExtendedEDAReport] = {}

    def put_report(self, report: PreM3ExtendedEDAReport) -> PreM3ExtendedEDAReport:
        with self._lock:
            existing = self.reports.get(report.report_id)
            if existing is not None and existing.fingerprint != report.fingerprint:
                raise ModelVersionImmutableError("Extended EDA reports are immutable.")
            if existing is not None:
                return existing
            self.reports[report.report_id] = report
            return report

    def get_report(
        self, *, tenant_id: str, project_id: str, report_id: str
    ) -> PreM3ExtendedEDAReport | None:
        report = self.reports.get(report_id)
        if report is None:
            return None
        if report.tenant_id != tenant_id or report.project_id != project_id:
            return None
        return report

    def list_for_cycle(
        self, *, tenant_id: str, project_id: str, cycle_id: str
    ) -> list[PreM3ExtendedEDAReport]:
        items = [
            item
            for item in self.reports.values()
            if item.tenant_id == tenant_id
            and item.project_id == project_id
            and item.cycle_id == cycle_id
        ]
        return sorted(items, key=lambda item: item.version, reverse=True)

    def latest_for_cycle(
        self, *, tenant_id: str, project_id: str, cycle_id: str
    ) -> PreM3ExtendedEDAReport | None:
        items = self.list_for_cycle(
            tenant_id=tenant_id, project_id=project_id, cycle_id=cycle_id
        )
        return items[0] if items else None

    def get_by_fingerprint(
        self, *, tenant_id: str, project_id: str, cycle_id: str, fingerprint: str
    ) -> PreM3ExtendedEDAReport | None:
        for item in self.list_for_cycle(
            tenant_id=tenant_id, project_id=project_id, cycle_id=cycle_id
        ):
            if item.fingerprint == fingerprint:
                return item
        return None


class FirestoreExtendedEDARepository:
    def __init__(self, client: Any) -> None:
        self._db = client

    def _ws(self, tenant_id: str, project_id: str):
        return (
            self._db.collection(COL_TENANTS)
            .document(tenant_id)
            .collection(COL_WORKSPACES)
            .document(project_id)
        )

    def put_report(self, report: PreM3ExtendedEDAReport) -> PreM3ExtendedEDAReport:
        existing = self.get_report(
            tenant_id=report.tenant_id,
            project_id=report.project_id,
            report_id=report.report_id,
        )
        if existing is not None and existing.fingerprint != report.fingerprint:
            raise ModelVersionImmutableError("Extended EDA reports are immutable.")
        if existing is not None:
            return existing
        self._ws(report.tenant_id, report.project_id).collection(COL_REPORTS).document(
            report.report_id
        ).set(model_to_document(report))
        self._db.collection(COL_INDEX).document(report.report_id).set(
            {
                "tenant_id": report.tenant_id,
                "workspace_id": report.project_id,
                "cycle_id": report.cycle_id,
                "fingerprint": report.fingerprint,
            }
        )
        return report

    def get_report(
        self, *, tenant_id: str, project_id: str, report_id: str
    ) -> PreM3ExtendedEDAReport | None:
        snap = (
            self._ws(tenant_id, project_id)
            .collection(COL_REPORTS)
            .document(report_id)
            .get()
        )
        if not snap.exists:
            return None
        report = document_to_model(PreM3ExtendedEDAReport, snap.to_dict())
        if report.tenant_id != tenant_id or report.project_id != project_id:
            return None
        return report

    def list_for_cycle(
        self, *, tenant_id: str, project_id: str, cycle_id: str
    ) -> list[PreM3ExtendedEDAReport]:
        items = [
            document_to_model(PreM3ExtendedEDAReport, snap.to_dict())
            for snap in self._ws(tenant_id, project_id).collection(COL_REPORTS).stream()
        ]
        matched = [
            item
            for item in items
            if item.tenant_id == tenant_id
            and item.project_id == project_id
            and item.cycle_id == cycle_id
        ]
        return sorted(matched, key=lambda item: item.version, reverse=True)

    def latest_for_cycle(
        self, *, tenant_id: str, project_id: str, cycle_id: str
    ) -> PreM3ExtendedEDAReport | None:
        items = self.list_for_cycle(
            tenant_id=tenant_id, project_id=project_id, cycle_id=cycle_id
        )
        return items[0] if items else None

    def get_by_fingerprint(
        self, *, tenant_id: str, project_id: str, cycle_id: str, fingerprint: str
    ) -> PreM3ExtendedEDAReport | None:
        for item in self.list_for_cycle(
            tenant_id=tenant_id, project_id=project_id, cycle_id=cycle_id
        ):
            if item.fingerprint == fingerprint:
                return item
        return None
