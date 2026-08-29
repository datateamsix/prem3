"""Extended EDA application service. Fail-soft interpretation; official EDA stays valid."""

from __future__ import annotations

from app.control_plane.ids import new_eda_report_id
from app.core.meridian_eda_contracts import MeridianEDAReceipt
from app.eda.compiler import compile_extended_eda_report
from app.eda.extended_contracts import (
    CUSTOMER_UPLOAD_HTML,
    TRUSTED_GENERATED_MERIDIAN_HTML,
    ExtendedEDABusinessContext,
    LabeledContextFact,
    OfficialReportView,
    PreM3ExtendedEDAReport,
)
from app.eda.html_trust import HtmlNotTrustedError, require_trusted_meridian_html
from app.eda.interpreter import EDAInterpreter
from app.eda.repository import ExtendedEDARepository, InMemoryExtendedEDARepository


class ExtendedEDAService:
    def __init__(
        self,
        repo: ExtendedEDARepository | None = None,
        *,
        interpreter: EDAInterpreter | None = None,
    ) -> None:
        self.repo = repo or InMemoryExtendedEDARepository()
        self.interpreter = interpreter
        self._html: dict[str, tuple[bytes, str, str]] = {}

    def compile_and_persist(
        self,
        *,
        tenant_id: str,
        project_id: str,
        cycle_id: str,
        track_id: str,
        receipt: MeridianEDAReceipt,
        official_html: bytes,
        official_html_ref: str,
        eda_receipt_ref: str,
        model_ready_manifest_ref: str | None = None,
        model_ready_fingerprint: str | None = None,
        business_context: ExtendedEDABusinessContext | None = None,
        data_foundation_facts: tuple[LabeledContextFact, ...] = (),
        data_foundation_fingerprint: str | None = None,
        official_html_artifact_class: str = TRUSTED_GENERATED_MERIDIAN_HTML,
        expected_html_sha256: str | None = None,
    ) -> PreM3ExtendedEDAReport:
        latest = self.repo.latest_for_cycle(
            tenant_id=tenant_id, project_id=project_id, cycle_id=cycle_id
        )
        next_version = 1 if latest is None else latest.version + 1
        compiled = compile_extended_eda_report(
            tenant_id=tenant_id,
            project_id=project_id,
            cycle_id=cycle_id,
            track_id=track_id,
            report_id=new_eda_report_id(),
            version=next_version,
            receipt=receipt,
            official_html=official_html,
            official_html_ref=official_html_ref,
            eda_receipt_ref=eda_receipt_ref,
            model_ready_manifest_ref=model_ready_manifest_ref,
            model_ready_fingerprint=model_ready_fingerprint,
            business_context=business_context,
            data_foundation_facts=data_foundation_facts,
            data_foundation_fingerprint=data_foundation_fingerprint,
            interpreter=self.interpreter,
            official_html_artifact_class=official_html_artifact_class,
            expected_html_sha256=expected_html_sha256,
        )
        existing = self.repo.get_by_fingerprint(
            tenant_id=tenant_id,
            project_id=project_id,
            cycle_id=cycle_id,
            fingerprint=compiled.fingerprint,
        )
        if existing is not None:
            return existing
        stored = self.repo.put_report(compiled)
        self._html[stored.source.official_html_sha256] = (
            official_html,
            official_html_artifact_class,
            stored.source.official_html_ref,
        )
        return stored

    def latest_for_cycle(
        self, *, tenant_id: str, project_id: str, cycle_id: str
    ) -> PreM3ExtendedEDAReport | None:
        return self.repo.latest_for_cycle(
            tenant_id=tenant_id, project_id=project_id, cycle_id=cycle_id
        )

    def official_report_view(
        self,
        report: PreM3ExtendedEDAReport,
        *,
        authorized_view_url: str,
    ) -> OfficialReportView:
        return OfficialReportView(
            official_report_available=True,
            content_type="text/html",
            authorized_view_url=authorized_view_url,
            sha256=report.source.official_html_sha256,
            artifact_class=report.official_html_artifact_class,
        )

    def load_trusted_html(
        self,
        *,
        tenant_id: str,
        project_id: str,
        cycle_id: str,
        artifact_class: str | None = None,
    ) -> tuple[bytes, PreM3ExtendedEDAReport]:
        report = self.latest_for_cycle(
            tenant_id=tenant_id, project_id=project_id, cycle_id=cycle_id
        )
        if report is None:
            raise KeyError("extended EDA report was not found")
        stored = self._html.get(report.source.official_html_sha256)
        if stored is None:
            raise HtmlNotTrustedError("Official HTML bytes are not available for this report.")
        payload, stored_class, stored_ref = stored
        requested = artifact_class or stored_class
        if requested == CUSTOMER_UPLOAD_HTML:
            raise HtmlNotTrustedError("Trusted Meridian HTML route rejects customer HTML.")
        if stored_ref != report.source.official_html_ref:
            raise HtmlNotTrustedError(
                "URI/hash mismatch: stored HTML ref does not match the report."
            )
        require_trusted_meridian_html(
            payload,
            artifact_class=requested,
            expected_sha256=report.source.official_html_sha256,
        )
        if report.tenant_id != tenant_id or report.project_id != project_id:
            raise KeyError("extended EDA report was not found")
        return payload, report
