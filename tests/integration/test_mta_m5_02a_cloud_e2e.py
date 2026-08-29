"""CLOUD_E2E: Cloud Tasks → OIDC launch → prem3-mta-worker → real DP6.

Requires RUN_CLOUD_E2E=1. On IAM/deploy failure the proof records
CLOUD_E2E_BLOCKED and this test fails with that status.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.cloud_e2e,
    pytest.mark.skipif(
        os.environ.get("RUN_CLOUD_E2E") != "1",
        reason="Set RUN_CLOUD_E2E=1 to attempt Cloud Tasks E2E",
    ),
]

REPO = Path(__file__).resolve().parents[2]
PROOF_PATH = REPO / "evaluation" / "meridian_music_center_mta_real_dp6_cloud_e2e_proof.json"
SCRIPT = REPO / "scripts" / "qualify_mta_real_dp6_cloud.py"


def test_cloud_tasks_real_dp6_e2e():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--execute"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    if not PROOF_PATH.is_file():
        pytest.fail(
            "Cloud E2E proof JSON was not written.\n"
            f"stdout:\n{proc.stdout[-2000:]}\nstderr:\n{proc.stderr[-2000:]}"
        )
    proof = json.loads(PROOF_PATH.read_text(encoding="utf-8"))
    if proof.get("status") == "PASSED":
        assert proof.get("cloud_tasks_oidc") is True
        return
    pytest.fail(
        f"{proof.get('status')}: {proof.get('reason')}\n"
        f"Proof: {PROOF_PATH}\n"
        f"exit={proc.returncode}"
    )
