from __future__ import annotations

import logging

from .models import DEFAULT_NAMESPACE, MANIFEST_DOC_ID, Manifest

logger = logging.getLogger(__name__)

_VERIFICATION_QUERIES: list[tuple[str, str]] = [
    ("deepidv platform overview modular identity verification", "docs:introduction"),
    ("create a verification session via API", "docs:api-reference/sessions/create-session"),
    ("webhook events notification endpoint", "docs:webhooks/overview"),
    ("authentication API key header", "docs:authentication"),
    ("verification link shareable workflow", "docs:workflows/verification-links"),
]


def verify(
    store,
    manifest: Manifest,
    namespace: str = DEFAULT_NAMESPACE,
    top_k: int = 20,
) -> bool:
    import pinecone

    pc = pinecone.Pinecone(api_key=store._api_key)
    all_passed = True

    indexed_doc_ids = {p.doc_id for p in manifest.pages}

    for query_text, expected_doc_id in _VERIFICATION_QUERIES:
        if expected_doc_id not in indexed_doc_ids:
            logger.warning("Skipping verification query for %s (not in manifest)", expected_doc_id)
            continue

        resp = pc.inference.embed(
            model="llama-text-embed-v2",
            inputs=[query_text],
            parameters={"input_type": "query", "truncate": "END"},
        )
        query_vector = resp[0]["values"]

        results = store._index.query(
            vector=query_vector,
            top_k=top_k,
            namespace=namespace,
            include_metadata=True,
            filter={"doc_id": {"$ne": MANIFEST_DOC_ID}},
        )

        matches = results.get("matches", [])
        found = any(
            m.get("metadata", {}).get("doc_id") == expected_doc_id for m in matches
        )

        if found:
            logger.info("VERIFY OK: query=%r found doc_id=%s", query_text, expected_doc_id)
        else:
            top_results = [m.get("metadata", {}).get("doc_id") for m in matches[:5]]
            logger.warning(
                "VERIFY SOFT FAIL: query=%r expected doc_id=%s not in top %d (top: %s)",
                query_text,
                expected_doc_id,
                top_k,
                top_results,
            )

    for page in manifest.pages:
        if page.status not in ("modified", "new"):
            continue
        resp = store._index.query(
            vector=[0.0] * store._get_dimension(),
            top_k=100,
            namespace=namespace,
            filter={"doc_id": {"$eq": page.doc_id}},
            include_metadata=True,
        )
        for m in resp.get("matches", []):
            stored_hash = m.get("metadata", {}).get("content_hash", "")
            if stored_hash != page.content_hash:
                logger.error(
                    "VERIFY FAIL: stale chunk %s has hash %s (expected %s)",
                    m["id"],
                    stored_hash,
                    page.content_hash,
                )
                all_passed = False

    return all_passed
