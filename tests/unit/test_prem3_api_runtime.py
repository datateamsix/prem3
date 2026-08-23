"""Runtime factory selection for prem3-api."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.control_plane.memory import InMemoryControlPlaneRepository
from app.service.app import create_app


def test_local_runtime_uses_in_memory_control_plane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PREM3_API_RUNTIME", "local")
    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "")
    monkeypatch.setenv("CLERK_SECRET_KEY", "")
    app = create_app()
    assert isinstance(app.state.control_plane, InMemoryControlPlaneRepository)
    body = TestClient(app).get("/readyz").json()
    assert body["status"] == "ready"
    assert body["dependencies"]["control_plane"] == "configured"
    assert body["dependencies"]["auth_provider"] == "not_configured"
    assert body["dependencies"]["billing_provider"] == "not_configured"


def test_injected_repository_wins_in_cloud_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PREM3_API_RUNTIME", "cloud")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
    repo = InMemoryControlPlaneRepository()
    app = create_app(control_plane_repository=repo)
    assert app.state.control_plane is repo


def test_cloud_runtime_constructs_firestore(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeFirestore:
        pass

    fake = _FakeFirestore()
    monkeypatch.setenv("PREM3_API_RUNTIME", "cloud")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "")
    monkeypatch.setenv("CLERK_SECRET_KEY", "")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
    monkeypatch.setattr(
        "app.service.runtime.FirestoreControlPlaneRepository.from_settings",
        lambda **_kwargs: fake,
    )
    monkeypatch.setattr("app.service.runtime.probe_firestore_control_plane", lambda _repo: None)
    app = create_app()
    assert app.state.control_plane is fake
    body = TestClient(app).get("/readyz").json()
    assert body["dependencies"]["control_plane"] == "configured"


def test_k_service_selects_cloud_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeFirestore:
        pass

    fake = _FakeFirestore()
    monkeypatch.delenv("PREM3_API_RUNTIME", raising=False)
    monkeypatch.setenv("K_SERVICE", "prem3-api")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "")
    monkeypatch.setenv("CLERK_SECRET_KEY", "")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
    monkeypatch.setattr(
        "app.service.runtime.FirestoreControlPlaneRepository.from_settings",
        lambda **_kwargs: fake,
    )
    monkeypatch.setattr("app.service.runtime.probe_firestore_control_plane", lambda _repo: None)
    app = create_app()
    assert app.state.control_plane is fake


def test_cloud_runtime_refuses_live_stripe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PREM3_API_RUNTIME", "cloud")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_example")
    monkeypatch.delenv("PREM3_ALLOW_STRIPE_LIVE", raising=False)
    with pytest.raises(RuntimeError, match="Live-mode Stripe"):
        create_app()


def test_health_is_process_liveness() -> None:
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
