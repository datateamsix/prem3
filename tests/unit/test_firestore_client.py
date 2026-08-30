"""Firestore Native default database must not be percent-encoded."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.control_plane.firestore_repo import (
    build_firestore_client,
    firestore_database_resource_name,
    normalize_firestore_database_id,
)


@pytest.mark.parametrize(
    "raw",
    ["(default)", '"(default)"', "'(default)'", "%28default%29", "  (default)  ", None, ""],
)
def test_normalize_firestore_database_id_default(raw: str | None) -> None:
    assert normalize_firestore_database_id(raw) == "(default)"


def test_firestore_database_resource_name_is_not_percent_encoded() -> None:
    name = firestore_database_resource_name("modelready-m3", "(default)")
    assert name == "projects/modelready-m3/databases/(default)"
    assert "%28" not in name
    assert "%29" not in name


def test_encoded_database_id_is_unquoted_in_resource_name() -> None:
    name = firestore_database_resource_name("modelready-m3", "%28default%29")
    assert name == "projects/modelready-m3/databases/(default)"


def test_build_firestore_client_overrides_encoded_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeClient:
        def __init__(self, *, project: str, database: str) -> None:
            self.project = project
            self._database = database
            self._database_string_internal = (
                f"projects/{project}/databases/%28default%29"
            )

    monkeypatch.setattr("app.control_plane.firestore_repo.firestore.Client", _FakeClient)
    client = build_firestore_client(
        project_id="modelready-m3",
        database='"(default)"',
    )
    assert client._database == "(default)"
    assert client._database_string_internal == (
        "projects/modelready-m3/databases/(default)"
    )


def test_service_package_init_does_not_import_fastapi() -> None:
    tree = ast.parse(Path("app/service/__init__.py").read_text(encoding="utf-8"))
    imports = [
        node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    assert imports == []
