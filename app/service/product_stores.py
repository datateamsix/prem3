"""Select CI/local InMemory stores or production Firestore stores."""

from __future__ import annotations

from app.business_iq.firestore import FirestoreBusinessIqStore
from app.business_iq.store import BusinessIqStore, InMemoryBusinessIqStore
from app.control_plane.firestore_repo import FirestoreControlPlaneRepository
from app.control_plane.repository import ControlPlaneRepository
from app.data_foundation.firestore_store import FirestoreDataFoundationStore
from app.data_foundation.store import DataFoundationStore, InMemoryDataFoundationStore
from app.identity_graph.firestore import FirestoreIdentityGraphStore
from app.identity_graph.store import IdentityGraphStore, InMemoryIdentityGraphStore


def build_product_stores(
    repo: ControlPlaneRepository,
) -> tuple[BusinessIqStore, DataFoundationStore]:
    if isinstance(repo, FirestoreControlPlaneRepository):
        return (
            FirestoreBusinessIqStore(repo.client),
            FirestoreDataFoundationStore(repo.client),
        )
    return InMemoryBusinessIqStore(), InMemoryDataFoundationStore()


def build_identity_graph_store(repo: ControlPlaneRepository) -> IdentityGraphStore:
    if isinstance(repo, FirestoreControlPlaneRepository):
        return FirestoreIdentityGraphStore(repo.client)
    return InMemoryIdentityGraphStore()
