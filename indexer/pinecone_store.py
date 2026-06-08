from __future__ import annotations

import json
import logging
from typing import Any

import pinecone

from .models import (
    DEFAULT_NAMESPACE,
    MANIFEST_CHUNK_ID,
    MANIFEST_DOC_ID,
    Manifest,
)

logger = logging.getLogger(__name__)


def _dummy_vector(dim: int) -> list[float]:
    v = [0.0] * dim
    v[0] = 1.0
    return v


class PineconeStore:
    def __init__(self, api_key: str, index_name: str) -> None:
        self._api_key = api_key
        self._pc = pinecone.Pinecone(api_key=api_key)
        self._index = self._pc.Index(index_name)

    def fetch_manifest(self, namespace: str = DEFAULT_NAMESPACE) -> Manifest | None:
        try:
            resp = self._index.fetch(
                ids=[MANIFEST_CHUNK_ID], namespace=namespace
            )
        except Exception:
            logger.warning("Failed to fetch manifest from Pinecone", exc_info=True)
            return None

        vectors = resp.get("vectors", {})
        if MANIFEST_CHUNK_ID not in vectors:
            return None

        metadata = vectors[MANIFEST_CHUNK_ID].get("metadata", {})
        manifest_json = metadata.get("manifest_json")
        if not manifest_json:
            return None

        try:
            data = json.loads(manifest_json)
            return Manifest.model_validate(data)
        except Exception:
            logger.warning("Failed to parse stored manifest", exc_info=True)
            return None

    def store_manifest(
        self, manifest: Manifest, namespace: str = DEFAULT_NAMESPACE
    ) -> None:
        manifest_json = manifest.model_dump_json()
        dim = self._index.describe_index_stats().get("dimension", 1024)
        vector = _dummy_vector(dim)

        self._index.upsert(
            vectors=[
                {
                    "id": MANIFEST_CHUNK_ID,
                    "values": vector,
                    "metadata": {
                        "source": manifest.source,
                        "doc_id": MANIFEST_DOC_ID,
                        "chunk_id": MANIFEST_CHUNK_ID,
                        "commit_sha": manifest.commit_sha,
                        "manifest_json": manifest_json,
                    },
                }
            ],
            namespace=namespace,
        )
        logger.info(
            "Stored manifest commit=%s pages=%d", manifest.commit_sha, len(manifest.pages)
        )

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
