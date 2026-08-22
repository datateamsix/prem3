"""Fake and real Google OAuth/Drive/BigQuery adapters used by prem3-api."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class GoogleTokenSet:
    access_token: str
    refresh_token: str | None
    granted_scopes: tuple[str, ...]
    google_subject: str
    display_email: str | None
    expires_in: int = 3600


@dataclass(frozen=True, slots=True)
class DriveFile:
    file_id: str
    name: str
    mime_type: str
    parents: tuple[str, ...]
    md5: str | None
    head_revision_id: str | None
    version: str | None
    size_bytes: int
    trashed: bool = False


@dataclass(frozen=True, slots=True)
class BigQueryTableInfo:
    project_id: str
    dataset_id: str
    table_id: str
    object_type: str
    schema_fingerprint: str
    etag: str
    last_modified: str
    num_bytes: int
    num_rows: int
    location: str


class GoogleOAuthProvider(Protocol):
    def authorization_url(
        self, *, state: str, scopes: tuple[str, ...], redirect_uri: str
    ) -> str: ...

    def exchange_code(self, *, code: str, redirect_uri: str) -> GoogleTokenSet: ...

    def refresh_access_token(self, *, refresh_token: str) -> str: ...

    def revoke(self, *, token: str) -> None: ...


class DriveClient(Protocol):
    def get_file(self, *, access_token: str, file_id: str) -> DriveFile | None: ...

    def create_folder(
        self, *, access_token: str, name: str, parent_id: str | None
    ) -> DriveFile: ...

    def list_children(self, *, access_token: str, folder_id: str) -> list[DriveFile]: ...

    def download_file(self, *, access_token: str, file_id: str) -> bytes: ...


class BigQueryClient(Protocol):
    def list_projects(self, *, access_token: str) -> list[dict[str, str]]: ...

    def list_datasets(self, *, access_token: str, project_id: str) -> list[dict[str, str]]: ...

    def list_tables(
        self, *, access_token: str, project_id: str, dataset_id: str
    ) -> list[BigQueryTableInfo]: ...

    def get_table(
        self, *, access_token: str, project_id: str, dataset_id: str, table_id: str
    ) -> BigQueryTableInfo | None: ...

    def get_dataset(
        self, *, access_token: str, project_id: str, dataset_id: str
    ) -> dict[str, Any] | None: ...

    def create_dataset(
        self,
        *,
        access_token: str,
        project_id: str,
        dataset_id: str,
        friendly_name: str,
        location: str,
    ) -> dict[str, Any]: ...

    def can_write_dataset(
        self, *, access_token: str, project_id: str, dataset_id: str
    ) -> bool: ...

    def query_preview(
        self, *, access_token: str, sql: str, max_rows: int = 5
    ) -> list[dict[str, Any]]: ...

    def get_table_physical(
        self, *, access_token: str, project_id: str, dataset_id: str, table_id: str
    ) -> dict[str, Any] | None: ...


class FakeGoogleOAuthProvider:
    def __init__(self) -> None:
        self.codes: dict[str, GoogleTokenSet] = {}
        self.revoked: list[str] = []
        self.authorization_urls: list[str] = []
        self.access_tokens: dict[str, str] = {}

    def seed_code(self, code: str, tokens: GoogleTokenSet) -> None:
        self.codes[code] = tokens
        if tokens.refresh_token:
            self.access_tokens[tokens.refresh_token] = tokens.access_token

    def authorization_url(self, *, state: str, scopes: tuple[str, ...], redirect_uri: str) -> str:
        url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
            {
                "response_type": "code",
                "access_type": "offline",
                "include_granted_scopes": "true",
                "prompt": "consent",
                "state": state,
                "redirect_uri": redirect_uri,
                "scope": " ".join(scopes),
            }
        )
        self.authorization_urls.append(url)
        return url

    def exchange_code(self, *, code: str, redirect_uri: str) -> GoogleTokenSet:
        del redirect_uri
        if code not in self.codes:
            raise ValueError("Unknown authorization code.")
        return self.codes[code]

    def refresh_access_token(self, *, refresh_token: str) -> str:
        return self.access_tokens.get(refresh_token, "ya29.fake-access")

    def revoke(self, *, token: str) -> None:
        self.revoked.append(token)


class FakeDriveClient:
    def __init__(self) -> None:
        self.files: dict[str, DriveFile] = {}
        self.created: list[str] = []

    def seed(self, file: DriveFile) -> None:
        self.files[file.file_id] = file

    def get_file(self, *, access_token: str, file_id: str) -> DriveFile | None:
        del access_token
        return self.files.get(file_id)

    def create_folder(
        self, *, access_token: str, name: str, parent_id: str | None
    ) -> DriveFile:
        del access_token
        file_id = f"folder_{len(self.files) + 1:04d}"
        folder = DriveFile(
            file_id=file_id,
            name=name,
            mime_type="application/vnd.google-apps.folder",
            parents=(parent_id,) if parent_id else (),
            md5=None,
            head_revision_id=None,
            version="1",
            size_bytes=0,
        )
        self.files[file_id] = folder
        self.created.append(file_id)
        return folder

    def list_children(self, *, access_token: str, folder_id: str) -> list[DriveFile]:
        del access_token
        return [item for item in self.files.values() if folder_id in item.parents]

    def download_file(self, *, access_token: str, file_id: str) -> bytes:
        del access_token
        found = self.files.get(file_id)
        if found is None:
            raise KeyError("Drive file not found.")
        return f"{found.name}".encode("utf-8")

    def trash(self, file_id: str) -> None:
        existing = self.files.get(file_id)
        if existing is None:
            return
        self.files[file_id] = DriveFile(
            file_id=existing.file_id,
            name=existing.name,
            mime_type=existing.mime_type,
            parents=existing.parents,
            md5=existing.md5,
            head_revision_id=existing.head_revision_id,
            version=existing.version,
            size_bytes=existing.size_bytes,
            trashed=True,
        )


class FakeBigQueryClient:
    def __init__(self) -> None:
        self.projects: list[dict[str, str]] = []
        self.datasets: dict[str, dict[str, Any]] = {}
        self.tables: dict[str, BigQueryTableInfo] = {}
        self.created_datasets: list[str] = []
        self.discovery_tokens: list[str] = []

    def list_projects(self, *, access_token: str) -> list[dict[str, str]]:
        self.discovery_tokens.append(access_token)
        return list(self.projects)

    def list_datasets(self, *, access_token: str, project_id: str) -> list[dict[str, str]]:
        self.discovery_tokens.append(access_token)
        rows = []
        for key, dataset in self.datasets.items():
            if key.startswith(f"{project_id}."):
                rows.append(
                    {
                        "project_id": project_id,
                        "dataset_id": dataset["dataset_id"],
                        "location": dataset.get("location", "US"),
                    }
                )
        return rows

    def list_tables(
        self, *, access_token: str, project_id: str, dataset_id: str
    ) -> list[BigQueryTableInfo]:
        self.discovery_tokens.append(access_token)
        prefix = f"{project_id}.{dataset_id}."
        return [item for key, item in self.tables.items() if key.startswith(prefix)]

    def get_table(
        self, *, access_token: str, project_id: str, dataset_id: str, table_id: str
    ) -> BigQueryTableInfo | None:
        self.discovery_tokens.append(access_token)
        return self.tables.get(f"{project_id}.{dataset_id}.{table_id}")

    def get_dataset(
        self, *, access_token: str, project_id: str, dataset_id: str
    ) -> dict[str, Any] | None:
        self.discovery_tokens.append(access_token)
        return self.datasets.get(f"{project_id}.{dataset_id}")

    def create_dataset(
        self,
        *,
        access_token: str,
        project_id: str,
        dataset_id: str,
        friendly_name: str,
        location: str,
    ) -> dict[str, Any]:
        self.discovery_tokens.append(access_token)
        key = f"{project_id}.{dataset_id}"
        if key in self.datasets:
            return self.datasets[key]
        payload = {
            "project_id": project_id,
            "dataset_id": dataset_id,
            "friendly_name": friendly_name,
            "location": location,
            "write_ok": True,
        }
        self.datasets[key] = payload
        self.created_datasets.append(key)
        return payload

    def seed_dataset(
        self,
        *,
        project_id: str,
        dataset_id: str,
        location: str = "US",
        write_ok: bool = False,
        friendly_name: str | None = None,
    ) -> None:
        self.datasets[f"{project_id}.{dataset_id}"] = {
            "project_id": project_id,
            "dataset_id": dataset_id,
            "friendly_name": friendly_name or dataset_id,
            "location": location,
            "write_ok": write_ok,
        }

    def can_write_dataset(
        self, *, access_token: str, project_id: str, dataset_id: str
    ) -> bool:
        self.discovery_tokens.append(access_token)
        dataset = self.datasets.get(f"{project_id}.{dataset_id}")
        return bool(dataset and dataset.get("write_ok"))

    def query_preview(
        self, *, access_token: str, sql: str, max_rows: int = 5
    ) -> list[dict[str, Any]]:
        self.discovery_tokens.append(access_token)
        if "select *" in sql.lower():
            raise ValueError("SELECT * is forbidden.")
        return [{"sql": sql, "row": index} for index in range(min(max_rows, 1))]

    def get_table_physical(
        self, *, access_token: str, project_id: str, dataset_id: str, table_id: str
    ) -> dict[str, Any] | None:
        table = self.get_table(
            access_token=access_token,
            project_id=project_id,
            dataset_id=dataset_id,
            table_id=table_id,
        )
        if table is None:
            return None
        return {
            "object_type": table.object_type,
            "num_rows": table.num_rows,
            "num_bytes": table.num_bytes,
            "location": table.location,
            "last_modified": table.last_modified,
            "partitioning_type": None,
            "clustering_fields": (),
        }


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files"
BQ_API = "https://bigquery.googleapis.com/bigquery/v2"


class RestGoogleOAuthProvider:
    """Authorization-code + refresh-token Google OAuth using the token endpoint."""

    def __init__(self, *, client_id: str, client_secret: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret

    def authorization_url(self, *, state: str, scopes: tuple[str, ...], redirect_uri: str) -> str:
        return GOOGLE_AUTH_URL + "?" + urlencode(
            {
                "client_id": self._client_id,
                "response_type": "code",
                "access_type": "offline",
                "include_granted_scopes": "true",
                "prompt": "consent",
                "state": state,
                "redirect_uri": redirect_uri,
                "scope": " ".join(scopes),
            }
        )

    def exchange_code(self, *, code: str, redirect_uri: str) -> GoogleTokenSet:
        payload = urlencode(
            {
                "code": code,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            }
        ).encode("utf-8")
        body = _post_form(GOOGLE_TOKEN_URL, payload)
        access_token = str(body.get("access_token") or "")
        if not access_token:
            raise ValueError("Google token exchange did not return an access token.")
        refresh = body.get("refresh_token")
        refresh_token = str(refresh) if refresh else None
        granted = tuple(str(body.get("scope") or "").split())
        subject, email = _userinfo(access_token)
        return GoogleTokenSet(
            access_token=access_token,
            refresh_token=refresh_token,
            granted_scopes=granted,
            google_subject=subject,
            display_email=email,
            expires_in=int(body.get("expires_in") or 3600),
        )

    def refresh_access_token(self, *, refresh_token: str) -> str:
        payload = urlencode(
            {
                "refresh_token": refresh_token,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "refresh_token",
            }
        ).encode("utf-8")
        body = _post_form(GOOGLE_TOKEN_URL, payload)
        access_token = str(body.get("access_token") or "")
        if not access_token:
            raise ValueError("Google refresh did not return an access token.")
        return access_token

    def revoke(self, *, token: str) -> None:
        payload = urlencode({"token": token}).encode("utf-8")
        request = Request(GOOGLE_REVOKE_URL, data=payload, method="POST")
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urlopen(request, timeout=15):
            return


def _post_form(url: str, payload: bytes) -> dict[str, Any]:
    request = Request(url, data=payload, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urlopen(request, timeout=15) as response:
        raw = response.read().decode("utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Google OAuth response was not an object.")
    return parsed


def _userinfo(access_token: str) -> tuple[str, str | None]:
    request = Request(GOOGLE_USERINFO_URL, method="GET")
    request.add_header("Authorization", f"Bearer {access_token}")
    with urlopen(request, timeout=15) as response:
        parsed = json.loads(response.read().decode("utf-8"))
    subject = str(parsed.get("sub") or "")
    if not subject:
        raise ValueError("Google userinfo did not return a subject.")
    email = parsed.get("email")
    return subject, str(email) if email else None


class RestDriveClient:
    """Live Drive adapter. Folder IDs remain authority."""

    def get_file(self, *, access_token: str, file_id: str) -> DriveFile | None:
        payload = _authorized_json(
            f"{DRIVE_FILES_URL}/{file_id}?fields=id,name,mimeType,parents,md5Checksum,headRevisionId,version,size,trashed",
            access_token=access_token,
        )
        if payload is None:
            return None
        return _drive_file_from_json(payload)

    def create_folder(
        self, *, access_token: str, name: str, parent_id: str | None
    ) -> DriveFile:
        body = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            body["parents"] = [parent_id]
        payload = _authorized_json(
            f"{DRIVE_FILES_URL}?fields=id,name,mimeType,parents,md5Checksum,headRevisionId,version,size,trashed",
            access_token=access_token,
            method="POST",
            json_body=body,
        )
        if payload is None:
            raise ValueError("Drive folder create failed.")
        return _drive_file_from_json(payload)

    def list_children(self, *, access_token: str, folder_id: str) -> list[DriveFile]:
        query = urlencode(
            {
                "q": f"'{folder_id}' in parents and trashed=false",
                "fields": "files(id,name,mimeType,parents,md5Checksum,headRevisionId,version,size,trashed)",
                "pageSize": "200",
            }
        )
        payload = _authorized_json(f"{DRIVE_FILES_URL}?{query}", access_token=access_token)
        files = payload.get("files") if payload else None
        if not isinstance(files, list):
            return []
        return [_drive_file_from_json(item) for item in files if isinstance(item, dict)]

    def download_file(self, *, access_token: str, file_id: str) -> bytes:
        return _authorized_bytes(f"{DRIVE_FILES_URL}/{file_id}?alt=media", access_token=access_token)


class RestBigQueryClient:
    """Live BigQuery adapter for metadata, preview, and depot writes."""

    def list_projects(self, *, access_token: str) -> list[dict[str, str]]:
        payload = _authorized_json(f"{BQ_API}/projects", access_token=access_token)
        rows = []
        for item in (payload or {}).get("projects") or []:
            rows.append(
                {
                    "project_id": str(item.get("projectReference", {}).get("projectId") or ""),
                    "friendly_name": str(item.get("friendlyName") or ""),
                }
            )
        return [item for item in rows if item["project_id"]]

    def list_datasets(self, *, access_token: str, project_id: str) -> list[dict[str, str]]:
        payload = _authorized_json(
            f"{BQ_API}/projects/{project_id}/datasets", access_token=access_token
        )
        rows = []
        for item in (payload or {}).get("datasets") or []:
            ref = item.get("datasetReference") or {}
            rows.append(
                {
                    "project_id": str(ref.get("projectId") or project_id),
                    "dataset_id": str(ref.get("datasetId") or ""),
                    "location": str(item.get("location") or "US"),
                }
            )
        return [item for item in rows if item["dataset_id"]]

    def list_tables(
        self, *, access_token: str, project_id: str, dataset_id: str
    ) -> list[BigQueryTableInfo]:
        payload = _authorized_json(
            f"{BQ_API}/projects/{project_id}/datasets/{dataset_id}/tables",
            access_token=access_token,
        )
        rows = []
        for item in (payload or {}).get("tables") or []:
            ref = item.get("tableReference") or {}
            table_id = str(ref.get("tableId") or "")
            if not table_id:
                continue
            detail = self.get_table(
                access_token=access_token,
                project_id=project_id,
                dataset_id=dataset_id,
                table_id=table_id,
            )
            if detail is not None:
                rows.append(detail)
        return rows

    def get_table(
        self, *, access_token: str, project_id: str, dataset_id: str, table_id: str
    ) -> BigQueryTableInfo | None:
        payload = self.get_table_physical(
            access_token=access_token,
            project_id=project_id,
            dataset_id=dataset_id,
            table_id=table_id,
        )
        if payload is None:
            return None
        return BigQueryTableInfo(
            project_id=project_id,
            dataset_id=dataset_id,
            table_id=table_id,
            object_type=str(payload.get("object_type") or "TABLE"),
            schema_fingerprint=str(payload.get("etag") or ""),
            etag=str(payload.get("etag") or ""),
            last_modified=str(payload.get("last_modified") or ""),
            num_bytes=int(payload.get("num_bytes") or 0),
            num_rows=int(payload.get("num_rows") or 0),
            location=str(payload.get("location") or "US"),
        )

    def get_dataset(
        self, *, access_token: str, project_id: str, dataset_id: str
    ) -> dict[str, Any] | None:
        return _authorized_json(
            f"{BQ_API}/projects/{project_id}/datasets/{dataset_id}",
            access_token=access_token,
        )

    def create_dataset(
        self,
        *,
        access_token: str,
        project_id: str,
        dataset_id: str,
        friendly_name: str,
        location: str,
    ) -> dict[str, Any]:
        existing = self.get_dataset(
            access_token=access_token, project_id=project_id, dataset_id=dataset_id
        )
        if existing is not None:
            return existing
        payload = _authorized_json(
            f"{BQ_API}/projects/{project_id}/datasets",
            access_token=access_token,
            method="POST",
            json_body={
                "datasetReference": {"projectId": project_id, "datasetId": dataset_id},
                "friendlyName": friendly_name,
                "location": location,
            },
        )
        if payload is None:
            raise ValueError("BigQuery dataset create failed.")
        return payload

    def can_write_dataset(
        self, *, access_token: str, project_id: str, dataset_id: str
    ) -> bool:
        return self.get_dataset(
            access_token=access_token, project_id=project_id, dataset_id=dataset_id
        ) is not None

    def query_preview(
        self, *, access_token: str, sql: str, max_rows: int = 5
    ) -> list[dict[str, Any]]:
        if "select *" in sql.lower():
            raise ValueError("SELECT * is forbidden.")
        payload = _authorized_json(
            f"{BQ_API}/projects/dummy/queries",
            access_token=access_token,
            method="POST",
            json_body={"query": sql, "useLegacySql": False, "maxResults": max_rows},
        )
        # jobs.query requires a real project; callers must pass project in SQL and URL.
        del payload
        raise ValueError("query_preview requires query_in_project.")

    def query_in_project(
        self, *, access_token: str, project_id: str, sql: str, max_rows: int = 5
    ) -> list[dict[str, Any]]:
        if "select *" in sql.lower():
            raise ValueError("SELECT * is forbidden.")
        payload = _authorized_json(
            f"{BQ_API}/projects/{project_id}/queries",
            access_token=access_token,
            method="POST",
            json_body={"query": sql, "useLegacySql": False, "maxResults": max_rows},
        )
        rows = []
        schema = [field.get("name") for field in ((payload or {}).get("schema") or {}).get("fields") or []]
        for row in (payload or {}).get("rows") or []:
            values = [cell.get("v") for cell in row.get("f") or []]
            rows.append({str(schema[index]): values[index] if index < len(values) else None for index in range(len(schema))})
        return rows

    def get_table_physical(
        self, *, access_token: str, project_id: str, dataset_id: str, table_id: str
    ) -> dict[str, Any] | None:
        payload = _authorized_json(
            f"{BQ_API}/projects/{project_id}/datasets/{dataset_id}/tables/{table_id}",
            access_token=access_token,
        )
        if payload is None:
            return None
        ref_type = str(payload.get("type") or "TABLE")
        partitioning = payload.get("timePartitioning") or payload.get("rangePartitioning") or {}
        clustering = payload.get("clustering") or {}
        return {
            "object_type": ref_type,
            "num_rows": int(payload.get("numRows") or 0),
            "num_bytes": int(payload.get("numBytes") or 0),
            "location": str(payload.get("location") or "US"),
            "last_modified": str(payload.get("lastModifiedTime") or ""),
            "etag": str(payload.get("etag") or ""),
            "partitioning_type": partitioning.get("type") if ref_type != "VIEW" else None,
            "partitioning_field": partitioning.get("field") if ref_type != "VIEW" else None,
            "clustering_fields": tuple(clustering.get("fields") or ()) if ref_type != "VIEW" else (),
        }


def _drive_file_from_json(payload: dict[str, Any]) -> DriveFile:
    parents = payload.get("parents") or ()
    return DriveFile(
        file_id=str(payload.get("id") or ""),
        name=str(payload.get("name") or ""),
        mime_type=str(payload.get("mimeType") or "application/octet-stream"),
        parents=tuple(str(item) for item in parents),
        md5=str(payload["md5Checksum"]) if payload.get("md5Checksum") else None,
        head_revision_id=str(payload["headRevisionId"]) if payload.get("headRevisionId") else None,
        version=str(payload["version"]) if payload.get("version") else None,
        size_bytes=int(payload.get("size") or 0),
        trashed=bool(payload.get("trashed")),
    )


def _authorized_json(
    url: str,
    *,
    access_token: str,
    method: str = "GET",
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    data = json.dumps(json_body).encode("utf-8") if json_body is not None else None
    request = Request(url, data=data, method=method)
    request.add_header("Authorization", f"Bearer {access_token}")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
    except Exception:
        return None
    if not raw:
        return {}
    parsed = json.loads(raw)
    return parsed if isinstance(parsed, dict) else None


def _authorized_bytes(url: str, *, access_token: str) -> bytes:
    request = Request(url, method="GET")
    request.add_header("Authorization", f"Bearer {access_token}")
    with urlopen(request, timeout=20) as response:
        return response.read()

