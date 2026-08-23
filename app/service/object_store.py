"""Object metadata readback for Dataset upload verification."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from google.cloud import storage


@dataclass(frozen=True, slots=True)
class ObjectMetadata:
    name: str
    size: int
    content_type: str | None
    generation: str
    etag: str | None
    crc32c: str | None
    md5_hash: str | None


class ObjectStore(Protocol):
    def get_object_metadata(self, *, bucket: str, object_name: str) -> ObjectMetadata | None: ...

    def write_json(
        self, *, bucket: str, object_name: str, payload: dict[str, Any]
    ) -> ObjectMetadata: ...

    def copy_object(
        self,
        *,
        bucket: str,
        source_object_name: str,
        dest_object_name: str,
        if_generation_match: int | None = 0,
    ) -> ObjectMetadata: ...

    def write_bytes(
        self,
        *,
        bucket: str,
        object_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> ObjectMetadata: ...

    def delete_prefix(self, *, bucket: str, prefix: str) -> int: ...


class FakeObjectStore:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], dict[str, Any]] = {}
        self.generation_counter = 1

    def put_bytes(
        self,
        *,
        bucket: str,
        object_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> ObjectMetadata:
        generation = str(self.generation_counter)
        self.generation_counter += 1
        record = {
            "size": len(data),
            "content_type": content_type,
            "generation": generation,
            "etag": f"etag-{generation}",
            "crc32c": f"crc-{generation}",
            "md5_hash": f"md5-{generation}",
            "data": data,
        }
        self.objects[(bucket, object_name)] = record
        return ObjectMetadata(
            name=object_name,
            size=record["size"],
            content_type=content_type,
            generation=generation,
            etag=record["etag"],
            crc32c=record["crc32c"],
            md5_hash=record["md5_hash"],
        )

    def write_bytes(
        self,
        *,
        bucket: str,
        object_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> ObjectMetadata:
        if (bucket, object_name) in self.objects:
            raise FileExistsError(object_name)
        return self.put_bytes(
            bucket=bucket,
            object_name=object_name,
            data=data,
            content_type=content_type,
        )

    def get_object_metadata(self, *, bucket: str, object_name: str) -> ObjectMetadata | None:
        record = self.objects.get((bucket, object_name))
        if record is None:
            return None
        return ObjectMetadata(
            name=object_name,
            size=int(record["size"]),
            content_type=str(record.get("content_type") or "") or None,
            generation=str(record["generation"]),
            etag=str(record.get("etag") or "") or None,
            crc32c=str(record.get("crc32c") or "") or None,
            md5_hash=str(record.get("md5_hash") or "") or None,
        )

    def write_json(
        self, *, bucket: str, object_name: str, payload: dict[str, Any]
    ) -> ObjectMetadata:
        return self.put_bytes(
            bucket=bucket,
            object_name=object_name,
            data=json.dumps(payload, sort_keys=True).encode("utf-8"),
            content_type="application/json",
        )

    def copy_object(
        self,
        *,
        bucket: str,
        source_object_name: str,
        dest_object_name: str,
        if_generation_match: int | None = 0,
    ) -> ObjectMetadata:
        source = self.objects.get((bucket, source_object_name))
        if source is None:
            raise FileNotFoundError(source_object_name)
        if if_generation_match == 0 and (bucket, dest_object_name) in self.objects:
            raise FileExistsError(dest_object_name)
        return self.put_bytes(
            bucket=bucket,
            object_name=dest_object_name,
            data=bytes(source["data"]),
            content_type=str(source.get("content_type") or "application/octet-stream"),
        )

    def delete_prefix(self, *, bucket: str, prefix: str) -> int:
        keys = [key for key in self.objects if key[0] == bucket and key[1].startswith(prefix)]
        for key in keys:
            del self.objects[key]
        return len(keys)


class GcsObjectStore:
    def __init__(self, *, client: storage.Client | None = None) -> None:
        self._client = client

    def _client_or_default(self) -> storage.Client:
        return self._client or storage.Client()

    def get_object_metadata(self, *, bucket: str, object_name: str) -> ObjectMetadata | None:
        blob = self._client_or_default().bucket(bucket).get_blob(object_name)
        if blob is None:
            return None
        return ObjectMetadata(
            name=object_name,
            size=int(blob.size or 0),
            content_type=blob.content_type,
            generation=str(blob.generation) if blob.generation is not None else "",
            etag=blob.etag,
            crc32c=blob.crc32c,
            md5_hash=blob.md5_hash,
        )

    def write_json(
        self, *, bucket: str, object_name: str, payload: dict[str, Any]
    ) -> ObjectMetadata:
        blob = self._client_or_default().bucket(bucket).blob(object_name)
        blob.upload_from_string(
            json.dumps(payload, sort_keys=True),
            content_type="application/json",
            if_generation_match=0,
        )
        blob.reload()
        return ObjectMetadata(
            name=object_name,
            size=int(blob.size or 0),
            content_type=blob.content_type,
            generation=str(blob.generation) if blob.generation is not None else "",
            etag=blob.etag,
            crc32c=blob.crc32c,
            md5_hash=blob.md5_hash,
        )

    def write_bytes(
        self,
        *,
        bucket: str,
        object_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> ObjectMetadata:
        blob = self._client_or_default().bucket(bucket).blob(object_name)
        blob.upload_from_string(
            data,
            content_type=content_type,
            if_generation_match=0,
        )
        blob.reload()
        return ObjectMetadata(
            name=object_name,
            size=int(blob.size or 0),
            content_type=blob.content_type,
            generation=str(blob.generation) if blob.generation is not None else "",
            etag=blob.etag,
            crc32c=blob.crc32c,
            md5_hash=blob.md5_hash,
        )

    def copy_object(
        self,
        *,
        bucket: str,
        source_object_name: str,
        dest_object_name: str,
        if_generation_match: int | None = 0,
    ) -> ObjectMetadata:
        client = self._client_or_default()
        source = client.bucket(bucket).blob(source_object_name)
        dest = client.bucket(bucket).blob(dest_object_name)
        token = None
        while True:
            token, _written, _total = dest.rewrite(
                source,
                token=token,
                if_generation_match=if_generation_match,
            )
            if token is None:
                break
        dest.reload()
        return ObjectMetadata(
            name=dest_object_name,
            size=int(dest.size or 0),
            content_type=dest.content_type,
            generation=str(dest.generation) if dest.generation is not None else "",
            etag=dest.etag,
            crc32c=dest.crc32c,
            md5_hash=dest.md5_hash,
        )

    def delete_prefix(self, *, bucket: str, prefix: str) -> int:
        client = self._client_or_default()
        deleted = 0
        for blob in client.list_blobs(bucket, prefix=prefix):
            blob.delete()
            deleted += 1
        return deleted
