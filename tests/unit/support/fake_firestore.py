"""In-process Firestore stand-in for durable-store unit tests. No live GCP."""

from __future__ import annotations

from typing import Any


class _Snapshot:
    def __init__(self, data: dict[str, Any] | None, doc_id: str) -> None:
        self._data = data
        self.exists = data is not None
        self.id = doc_id

    def to_dict(self) -> dict[str, Any] | None:
        return dict(self._data) if self._data is not None else None


class FakeDocument:
    def __init__(self, db: dict[str, dict[str, Any]], path: str) -> None:
        self._db = db
        self._path = path

    def set(self, data: dict[str, Any]) -> None:
        self._db[self._path] = dict(data)

    def get(self) -> _Snapshot:
        return _Snapshot(self._db.get(self._path), self._path.rsplit("/", 1)[-1])

    def collection(self, name: str) -> FakeCollection:
        return FakeCollection(self._db, f"{self._path}/{name}")


class FakeCollection:
    def __init__(self, db: dict[str, dict[str, Any]], prefix: str) -> None:
        self._db = db
        self._prefix = prefix

    def document(self, doc_id: str) -> FakeDocument:
        return FakeDocument(self._db, f"{self._prefix}/{doc_id}")

    def stream(self):
        prefix = f"{self._prefix}/"
        for path, data in list(self._db.items()):
            if path.startswith(prefix) and "/" not in path[len(prefix) :]:
                yield _Snapshot(data, path[len(prefix) :])


class FakeFirestore:
    def __init__(self) -> None:
        self._docs: dict[str, dict[str, Any]] = {}

    def collection(self, name: str) -> FakeCollection:
        return FakeCollection(self._docs, name)
