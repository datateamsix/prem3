"""In-process Firestore stand-in for durable-store unit tests. No live GCP."""

from __future__ import annotations

from threading import Lock
from typing import Any


class _Snapshot:
    def __init__(self, data: dict[str, Any] | None, doc_id: str) -> None:
        self._data = data
        self.exists = data is not None
        self.id = doc_id

    def to_dict(self) -> dict[str, Any] | None:
        return dict(self._data) if self._data is not None else None


class FakeDocument:
    def __init__(self, db: dict[str, dict[str, Any]], path: str, lock: Lock) -> None:
        self._db = db
        self._path = path
        self._lock = lock

    def set(self, data: dict[str, Any]) -> None:
        with self._lock:
            self._db[self._path] = dict(data)

    def create(self, data: dict[str, Any]) -> None:
        with self._lock:
            if self._path in self._db:
                raise FileExistsError(self._path)
            self._db[self._path] = dict(data)

    def get(self, transaction: Any = None) -> _Snapshot:
        del transaction
        with self._lock:
            return _Snapshot(self._db.get(self._path), self._path.rsplit("/", 1)[-1])

    def delete(self) -> None:
        with self._lock:
            self._db.pop(self._path, None)

    def collection(self, name: str) -> FakeCollection:
        return FakeCollection(self._db, f"{self._path}/{name}", self._lock)


class FakeCollection:
    def __init__(self, db: dict[str, dict[str, Any]], prefix: str, lock: Lock) -> None:
        self._db = db
        self._prefix = prefix
        self._lock = lock

    def document(self, doc_id: str) -> FakeDocument:
        return FakeDocument(self._db, f"{self._prefix}/{doc_id}", self._lock)

    def stream(self):
        prefix = f"{self._prefix}/"
        with self._lock:
            items = list(self._db.items())
        for path, data in items:
            if path.startswith(prefix) and "/" not in path[len(prefix) :]:
                yield _Snapshot(data, path[len(prefix) :])


class FakeFirestore:
    def __init__(self) -> None:
        self._docs: dict[str, dict[str, Any]] = {}
        self._lock = Lock()

    def collection(self, name: str) -> FakeCollection:
        return FakeCollection(self._docs, name, self._lock)
