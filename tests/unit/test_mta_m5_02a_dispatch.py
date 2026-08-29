"""Cloud Run Job extra env for prem3-mta-worker."""

from __future__ import annotations

from app.modeling.mta.contracts import AttributionModelId
from app.modeling.mta.jobs import (
    MTA_CLOUD_RUNTIME_ENV,
    MTA_DISPATCH_ENV,
    CloudRunMTAJobLauncher,
)
from app.modeling.mta.models_registry import default_enabled_models
from app.modeling.mta.results_contracts import MTAComputationAuthority as ResultAuth
from app.modeling.mta.runtime_contracts import MTAComputationAuthority as RuntimeAuth


class _FakeJobsClient:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    def run_job(self, request=None, **_kwargs):
        self.requests.append(request)

        class _Meta:
            name = "projects/p/locations/l/jobs/prem3-mta-worker/executions/exec-1"

        class _Op:
            metadata = _Meta()

            def done(self):
                return True

            def result(self, timeout=1):
                del timeout
                return type("R", (), {"name": _Meta.name})()

        return _Op()


def test_cloud_run_mta_launcher_sets_cloud_runtime_env():
    client = _FakeJobsClient()
    launcher = CloudRunMTAJobLauncher(
        project_id="modelready-m3",
        location="us-central1",
        client=client,
    )
    name = launcher.launch("mtdsp_demo")
    assert name == "exec-1"
    env = client.requests[0]["overrides"]["container_overrides"][0]["env"]
    names = {item["name"]: item["value"] for item in env}
    assert names[MTA_DISPATCH_ENV] == "mtdsp_demo"
    assert names[MTA_CLOUD_RUNTIME_ENV] == "1"


def test_computation_authority_enum_is_shared():
    assert ResultAuth is RuntimeAuth


def test_default_enabled_models_include_last_non_direct():
    assert AttributionModelId.LAST_NON_DIRECT in default_enabled_models()
