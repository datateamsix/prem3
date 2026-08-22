"""Select CI/local InMemory stores or production Firestore stores."""

from __future__ import annotations

from app.business_iq.firestore import FirestoreBusinessIqStore
from app.business_iq.store import BusinessIqStore, InMemoryBusinessIqStore
from app.control_plane.firestore_repo import FirestoreControlPlaneRepository
from app.control_plane.repository import ControlPlaneRepository
from app.data_foundation.firestore_store import FirestoreDataFoundationStore
from app.data_foundation.store import DataFoundationStore, InMemoryDataFoundationStore


def build_product_stores(
    repo: ControlPlaneRepository,
) -> tuple[BusinessIqStore, DataFoundationStore]:
    if isinstance(repo, FirestoreControlPlaneRepository):
        return (
            FirestoreBusinessIqStore(repo.client),
            FirestoreDataFoundationStore(repo.client),
        )
    return InMemoryBusinessIqStore(), InMemoryDataFoundationStore()
