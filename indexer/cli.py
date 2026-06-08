from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from .chunker import chunk_text
from .diff import compute_diff
from .embedder import Embedder
from .manifest import build_manifest
from .models import DEFAULT_NAMESPACE, SOURCE_OPENAPI, ManifestPage, PageStatus
from .normalizer import extract_frontmatter, normalize
from .pinecone_store import PineconeStore
from .verifier import verify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _get_commit_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()[:12]
    except Exception:
        return os.environ.get("GITHUB_SHA", "unknown")[:12]


def _index_page(
    page: ManifestPage,
    docs_root: Path,
    commit_sha: str,
    store: PineconeStore,
    embedder: Embedder,
    namespace: str,
    openapi_text_cache: dict[str, str] | None = None,
) -> int:
    if page.source == SOURCE_OPENAPI:
        normalized = openapi_text_cache.get(page.doc_id, "") if openapi_text_cache else ""
    else:
        mdx_path = docs_root / page.path
        raw = mdx_path.read_text(encoding="utf-8")
        _frontmatter, body = extract_frontmatter(raw)
        normalized = normalize(body)

    chunks = chunk_text(
        text=normalized,
        doc_id=page.doc_id,
        path=page.path,
        route=page.route,
        url=page.canonical_url,
        title=page.title,
        description=page.description,
        content_hash=page.content_hash,
        commit_sha=commit_sha,
        source=page.source,
        method=page.method,
    )

    if not chunks:
        page.chunk_count = 0
        return 0

    records = embedder.embed_chunks(chunks)
    store.upsert_records(records, namespace=namespace)
    page.chunk_count = len(chunks)
    return len(chunks)


def run(
    docs_root: Path,
    api_key: str,
    index_name: str,
    namespace: str = DEFAULT_NAMESPACE,
    skip_verify: bool = False,
    openapi_spec_path: str | None = None,
) -> int:
    commit_sha = _get_commit_sha()
    start = time.monotonic()
    logger.info("Starting docs indexing commit=%s namespace=%s", commit_sha, namespace)

    store = PineconeStore(api_key=api_key, index_name=index_name)
    embedder = Embedder(api_key=api_key)

    current_manifest = build_manifest(
        docs_root, commit_sha, namespace, openapi_spec_path=openapi_spec_path
    )
    logger.info(
        "Built manifest: %d pages commit=%s", len(current_manifest.pages), commit_sha
    )

    openapi_text_cache: dict[str, str] = {}
    if openapi_spec_path:
        from .openapi_normalizer import parse_spec
        for op in parse_spec(openapi_spec_path):
            openapi_text_cache[op.doc_id] = op.text
        logger.info("Parsed OpenAPI spec: %d operations", len(openapi_text_cache))

    previous_manifest = store.fetch_manifest(namespace)
    if previous_manifest:
        logger.info(
            "Found previous manifest: %d pages commit=%s",
            len(previous_manifest.pages),
            previous_manifest.commit_sha,
        )
    else:
        logger.info("No previous manifest found — full index build")

    diff = compute_diff(current_manifest, previous_manifest)

    logger.info(
        "Diff: new=%d modified=%d unchanged=%d removed=%d",
        len(diff.new),
        len(diff.modified),
        len(diff.unchanged),
        len(diff.removed),
    )

    if not diff.has_changes:
        logger.info("No changes detected — nothing to do")
        return 0

    for page in diff.removed:
        count = store.delete_by_doc_id(page.doc_id, namespace)
        logger.info("Removed page %s (%d vectors deleted)", page.doc_id, count)

    for page in diff.modified:
        count = store.delete_by_doc_id(page.doc_id, namespace)
        logger.info("Cleared %d stale vectors for modified page %s", count, page.doc_id)

    pages_to_index = diff.new + diff.modified
    total_chunks = 0

    for page in pages_to_index:
        n = _index_page(page, docs_root, commit_sha, store, embedder, namespace, openapi_text_cache)
        total_chunks += n
        logger.info("Indexed %s: %d chunks", page.doc_id, n)

    for page in diff.unchanged:
        prev = previous_manifest.page_by_doc_id(page.doc_id) if previous_manifest else None
        page.chunk_count = prev.chunk_count if prev else 0

    for page in current_manifest.pages:
        page.status = PageStatus.INDEXED

    current_manifest.generated_at = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    ).isoformat()

    store.store_manifest(current_manifest, namespace)

    if not skip_verify:
        passed = verify(store, current_manifest, namespace)
        if not passed:
            logger.error("Verification queries failed — aborting")
            return 1

    logger.info(
        "Indexing complete: %d pages indexed, %d total chunks, commit=%s, time=%.1fs",
        len(pages_to_index),
        total_chunks,
        commit_sha,
        time.monotonic() - start,
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Index deepidv docs into Pinecone")
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=Path("."),
        help="Root directory of the Mintlify docs project",
    )
    parser.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    parser.add_argument("--skip-verify", action="store_true")
    parser.add_argument("--openapi-spec", default=None, help="Path to OpenAPI YAML spec file")
    parser.add_argument("--api-key", default=os.environ.get("PINECONE_API_KEY", ""))
    parser.add_argument("--index-name", default=os.environ.get("PINECONE_INDEX_NAME", ""))

    args = parser.parse_args()

    if not args.api_key:
        logger.error("PINECONE_API_KEY is required (set env var or pass --api-key)")
        sys.exit(1)
    if not args.index_name:
        logger.error("PINECONE_INDEX_NAME is required (set env var or pass --index-name)")
        sys.exit(1)

    rc = run(
        docs_root=args.docs_root,
        api_key=args.api_key,
        index_name=args.index_name,
        namespace=args.namespace,
        skip_verify=args.skip_verify,
        openapi_spec_path=args.openapi_spec,
    )
    sys.exit(rc)


if __name__ == "__main__":
    main()
