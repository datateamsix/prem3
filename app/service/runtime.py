"""prem3-api runtime selection.

Local default remains in-memory and fail-closed. Cloud Run must opt into
Firestore through ``PREM3_API_RUNTIME=cloud`` or the platform ``K_SERVICE``
variable. Import success is not provider selection.
"""

from __future__ import annotations

import os

from app.config import Settings
from app.control_plane.firestore_repo import FirestoreControlPlaneRepository
from app.control_plane.memory import InMemoryControlPlaneRepository
from app.control_plane.repository import ControlPlaneRepository

CLOUD_RUNTIME_VALUES = frozenset({"cloud", "production"})
LOCAL_RUNTIME_VALUES = frozenset({"local", "test", "ci"})
FIRESTORE_PROBE_TENANT_ID = "tnt_prem3_readiness_probe"


def uses_cloud_runtime() -> bool:
    explicit = os.getenv("PREM3_API_RUNTIME", "").strip().lower()
    if explicit in CLOUD_RUNTIME_VALUES:
        return True
    if explicit in LOCAL_RUNTIME_VALUES:
        return False
    return bool(os.getenv("K_SERVICE", "").strip())


def assert_provider_mode_safe(settings: Settings) -> None:
    """Refuse live Stripe/Clerk credentials in cloud runtime unless explicitly allowed."""
    if not uses_cloud_runtime():
        return
    stripe_key = settings.stripe_secret_key or ""
    if stripe_key.startswith("sk_live_") and os.getenv("PREM3_ALLOW_STRIPE_LIVE") != "1":
        raise RuntimeError(
            "Live-mode Stripe credentials refused for prem3-api cloud runtime."
        )
    clerk_key = settings.clerk_secret_key or ""
    if clerk_key.startswith("sk_live_") and os.getenv("PREM3_ALLOW_CLERK_LIVE") != "1":
        raise RuntimeError(
            "Clerk production instance refused for prem3-api cloud runtime."
        )


def probe_firestore_control_plane(repo: FirestoreControlPlaneRepository) -> None:
    """Non-destructive Firestore IAM/reachability probe. Does not create documents."""
    repo.get_tenant(FIRESTORE_PROBE_TENANT_ID)


def build_control_plane(
    settings: Settings,
    injected: ControlPlaneRepository | None,
) -> tuple[ControlPlaneRepository, str]:
    """Return ``(repository, status)`` for readiness reporting.

    ``status`` is ``configured`` or ``not_configured``. Cloud runtime fails
    startup when Firestore cannot be constructed or probed.
    """
    if injected is not None:
        return injected, "configured"
    if not uses_cloud_runtime():
        return InMemoryControlPlaneRepository(), "configured"
    try:
        repo = FirestoreControlPlaneRepository.from_settings(
            project_id=settings.project_id,
            database=settings.firestore_database,
        )
        probe_firestore_control_plane(repo)
    except Exception as exc:  # noqa: BLE001 — cloud startup must fail closed on any probe error
        raise RuntimeError(
            "Cloud runtime requires a reachable Firestore control plane "
            f"({type(exc).__name__}: {exc})."
        ) from exc
    return repo, "configured"
