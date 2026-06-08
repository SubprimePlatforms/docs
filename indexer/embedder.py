from __future__ import annotations

import logging
from typing import Any

from .models import ChunkRecord

logger = logging.getLogger(__name__)

_EMBED_MODEL = "llama-text-embed-v2"
_BATCH_SIZE = 50


class Embedder:
    def __init__(self, api_key: str) -> None:
        import pinecone

        self._pc = pinecone.Pinecone(api_key=api_key)

    def embed_chunks(
        self, chunks: list[ChunkRecord]
    ) -> list[dict[str, Any]]:
        texts = [c.text for c in chunks]
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
            resp = self._pc.inference.embed(
                model=_EMBED_MODEL,
                inputs=batch,
                parameters={"input_type": "passage", "truncate": "END"},
            )
            all_embeddings.extend([r["values"] for r in resp])

        records: list[dict[str, Any]] = []
        for chunk, embedding in zip(chunks, all_embeddings):
            records.append(
                {
                    "id": chunk.chunk_id,
                    "values": embedding,
                    "metadata": {
                        "source": chunk.source,
                        "doc_id": chunk.doc_id,
                        "chunk_id": chunk.chunk_id,
                        "path": chunk.path,
                        "route": chunk.route,
                        "url": chunk.url,
                        "title": chunk.title,
                        "description": chunk.description,
                        "content_hash": chunk.content_hash,
                        "commit_sha": chunk.commit_sha,
                        "section": chunk.section,
                        "chunk_index": chunk.chunk_index,
                        "text": chunk.text,
                        **({"method": chunk.method} if chunk.method else {}),
                    },
                }
            )

        logger.info("Embedded %d chunks", len(records))
        return records
