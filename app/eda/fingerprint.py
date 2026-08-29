"""Version fingerprints for PreM3 extended EDA reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.meridian_eda_contracts import MeridianEDAReceipt, canonical_json_fingerprint
from app.eda.extended_contracts import INTERPRETATION_POLICY_VERSION

_INTEL_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "context"
    / "intelligence"
    / "intelligence_version.json"
)


def knowledge_version() -> str:
    payload = json.loads(_INTEL_PATH.read_text(encoding="utf-8"))
    return str(payload["intelligence_version"])


def eda_receipt_fingerprint(receipt: MeridianEDAReceipt) -> str:
    return canonical_json_fingerprint(
        {
            "run_id": receipt.run_id,
            "status": receipt.status,
            "html_report_uri": receipt.html_report_uri,
            "model_input_fingerprint": receipt.model_input_fingerprint,
            "findings": [item.model_dump(mode="json") for item in receipt.findings],
            "severity_summary": receipt.severity_summary,
            "model_spec": receipt.model_spec.model_dump(mode="json"),
            "data_adequacy": receipt.data_adequacy.model_dump(mode="json"),
            "compatibility_event": None
            if receipt.compatibility_event is None
            else receipt.compatibility_event.model_dump(mode="json"),
            "meridian": receipt.meridian,
        }
    )


def report_fingerprint(payload: dict[str, Any]) -> str:
    return canonical_json_fingerprint(payload)


def version_binding(
    *,
    eda_receipt_fingerprint_value: str,
    official_html_sha256: str,
    model_ready_fingerprint: str | None,
    business_profile_snapshot_id: str | None,
    data_foundation_fingerprint: str | None,
    knowledge_version_value: str,
    interpretation_policy_version: str = INTERPRETATION_POLICY_VERSION,
    interpretation_digest: str,
) -> dict[str, Any]:
    return {
        "eda_receipt_fingerprint": eda_receipt_fingerprint_value,
        "official_html_sha256": official_html_sha256,
        "model_ready_fingerprint": model_ready_fingerprint,
        "business_profile_snapshot_id": business_profile_snapshot_id,
        "data_foundation_fingerprint": data_foundation_fingerprint,
        "knowledge_version": knowledge_version_value,
        "interpretation_policy_version": interpretation_policy_version,
        "interpretation_digest": interpretation_digest,
    }
