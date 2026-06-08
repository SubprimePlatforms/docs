from __future__ import annotations

import json
import logging
from typing import Any

import pinecone

from .models import (
    DEFAULT_NAMESPACE,
    MANIFEST_CHUNK_PREFIX,
    MANIFEST_DOC_ID,
    MANIFEST_SHARD_SIZE,
    Manifest,
)

logger = logging.getLogger(__name__)

_MAX_METADATA_BYTES = 36_000


def _dummy_vector(dim: int) -> list[float]:
    v = [0.0] * dim
    v[0] = 1.0
    return v


def _shard_id(index: int) -> str:
    return f"{MANIFEST_CHUNK_PREFIX}:{index:04d}"


def _all_shard_ids(count: int) -> list[str]:
    return [_shard_id(i) for i in range(count)]


class PineconeStore:
    def __init__(self, api_key: str, index_name: str) -> None:
        self._api_key = api_key
        self._pc = pinecone.Pinecone(api_key=api_key)
        self._index = self._pc.Index(index_name)

    def fetch_manifest(self, namespace: str = DEFAULT_NAMESPACE) -> Manifest | None:
        try:
            stats = self._index.describe_index_stats()
            dim = stats.get("dimension", 1024)
            resp = self._index.query(
                vector=_dummy_vector(dim),
                top_k=100,
                namespace=namespace,
                filter={"doc_id": {"$eq": MANIFEST_DOC_ID}},
                include_metadata=True,
            )
        except Exception:
            logger.warning("Failed to fetch manifest from Pinecone", exc_info=True)
            return None

        matches = resp.get("matches", [])
        if not matches:
            return None

        header = None
        shards: dict[int, list[dict]] = {}

        for m in matches:
            meta = m.get("metadata", {})
            shard_index = meta.get("shard_index")
            if shard_index is None:
                continue
            if shard_index == -1:
                header = meta
            else:
                page_json = meta.get("pages_json", "[]")
                try:
                    shards[int(shard_index)] = json.loads(page_json)
                except (json.JSONDecodeError, ValueError):
                    logger.warning("Failed to parse manifest shard %d", shard_index)

        if header is None:
            return None

        all_pages: list[dict] = []
        for idx in sorted(shards.keys()):
            all_pages.extend(shards[idx])

        try:
            data = {
                "schema_version": header.get("schema_version", 1),
                "source": header.get("source", "deepidv-docs"),
                "commit_sha": header.get("commit_sha", ""),
                "namespace": header.get("namespace", DEFAULT_NAMESPACE),
                "generated_at": header.get("generated_at", ""),
                "pages": all_pages,
            }
            return Manifest.model_validate(data)
        except Exception:
            logger.warning("Failed to parse stored manifest", exc_info=True)
            return None

    def store_manifest(
        self, manifest: Manifest, namespace: str = DEFAULT_NAMESPACE
    ) -> None:
        dim = self._get_dimension()
        vector = _dummy_vector(dim)

        pages_data = [p.model_dump() for p in manifest.pages]

        header_meta: dict[str, Any] = {
            "source": manifest.source,
            "doc_id": MANIFEST_DOC_ID,
            "chunk_id": _shard_id(-1),
            "shard_index": -1,
            "schema_version": manifest.schema_version,
            "commit_sha": manifest.commit_sha,
            "namespace": manifest.namespace,
            "generated_at": manifest.generated_at,
            "total_pages": len(manifest.pages),
        }

        shards: list[list[dict]] = []
        current_shard: list[dict] = []
        current_size = len(json.dumps(header_meta))

        for page in pages_data:
            page_json = json.dumps([page])
            if current_size + len(page_json) > _MAX_METADATA_BYTES and current_shard:
                shards.append(current_shard)
                current_shard = []
                current_size = 0
            current_shard.append(page)
            current_size += len(page_json)

        if current_shard:
            shards.append(current_shard)

        vectors: list[dict] = [
            {
                "id": _shard_id(-1),
                "values": vector,
                "metadata": header_meta,
            }
        ]

        for i, shard in enumerate(shards):
            vectors.append(
                {
                    "id": _shard_id(i),
                    "values": vector,
                    "metadata": {
                        "source": manifest.source,
                        "doc_id": MANIFEST_DOC_ID,
                        "chunk_id": _shard_id(i),
                        "shard_index": i,
                        "commit_sha": manifest.commit_sha,
                        "pages_json": json.dumps(shard),
                    },
                }
            )

        old_ids = self._find_manifest_ids(namespace)
        self._index.upsert(vectors=vectors, namespace=namespace)

        new_ids = {v["id"] for v in vectors}
        stale = [oid for oid in old_ids if oid not in new_ids]
        if stale:
            self._index.delete(ids=stale, namespace=namespace)
            logger.info("Cleaned up %d stale manifest shards", len(stale))

        logger.info(
            "Stored manifest commit=%s pages=%d shards=%d",
            manifest.commit_sha,
            len(manifest.pages),
            len(shards),
        )

    def _find_manifest_ids(self, namespace: str) -> list[str]:
        try:
            dim = self._get_dimension()
            resp = self._index.query(
                vector=_dummy_vector(dim),
                top_k=100,
                namespace=namespace,
                filter={"doc_id": {"$eq": MANIFEST_DOC_ID}},
                include_metadata=False,
            )
            return [m["id"] for m in resp.get("matches", [])]
        except Exception:
            return []

    def delete_by_doc_id(self, doc_id: str, namespace: str = DEFAULT_NAMESPACE) -> int:
        prefix = f"{doc_id}:"
        resp = self._index.query(
            vector=_dummy_vector(self._get_dimension()),
            top_k=10000,
            namespace=namespace,
            filter={"doc_id": {"$eq": doc_id}},
            include_metadata=False,
        )

        ids_to_delete = [m["id"] for m in resp.get("matches", []) if m["id"].startswith(prefix)]
        if not ids_to_delete:
            return 0

        self._index.delete(ids=ids_to_delete, namespace=namespace)
        logger.info("Deleted %d vectors for doc_id=%s", len(ids_to_delete), doc_id)
        return len(ids_to_delete)

    def upsert_records(
        self,
        records: list[dict[str, Any]],
        namespace: str = DEFAULT_NAMESPACE,
        batch_size: int = 100,
    ) -> None:
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            self._index.upsert(vectors=batch, namespace=namespace)
            logger.info("Upserted batch %d-%d/%d", i, i + len(batch), len(records))

    def _get_dimension(self) -> int:
        stats = self._index.describe_index_stats()
        return stats.get("dimension", 1024)
