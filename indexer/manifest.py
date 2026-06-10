from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .hashing import content_hash
from .models import (
    API_BASE_URL,
    BASE_URL,
    DEFAULT_NAMESPACE,
    SOURCE,
    SOURCE_OPENAPI,
    Manifest,
    ManifestPage,
    PageStatus,
)
from .normalizer import extract_frontmatter, normalize
from .openapi_normalizer import parse_spec


def _parse_navigation(docs_json: dict) -> list[str]:
    pages: list[str] = []
    for tab in docs_json.get("navigation", {}).get("tabs", []):
        for group in tab.get("groups", []):
            for page in group.get("pages", []):
                pages.append(page)
    return pages


def _page_to_doc_id(page: str) -> str:
    return f"docs:{page}"


def _page_to_route(page: str) -> str:
    return f"/{page}"


def _page_to_url(page: str) -> str:
    return f"{BASE_URL}/{page}"


def _page_to_path(page: str) -> str:
    return f"{page}.mdx"


def build_manifest(
    docs_root: Path,
    commit_sha: str,
    namespace: str = DEFAULT_NAMESPACE,
    openapi_spec_path: str | None = None,
) -> Manifest:
    docs_json_path = docs_root / "docs.json"
    with open(docs_json_path, encoding="utf-8") as f:
        docs_json = json.load(f)

    page_slugs = _parse_navigation(docs_json)
    manifest_pages: list[ManifestPage] = []

    for slug in page_slugs:
        mdx_path = docs_root / _page_to_path(slug)
        if not mdx_path.exists():
            continue

        raw = mdx_path.read_text(encoding="utf-8")
        frontmatter, body = extract_frontmatter(raw)
        normalized = normalize(body)

        doc_id = _page_to_doc_id(slug)
        route = _page_to_route(slug)
        url = _page_to_url(slug)
        path = _page_to_path(slug)
        title = frontmatter.get("title", slug)
        description = frontmatter.get("description", "")
        c_hash = content_hash(normalized)

        manifest_pages.append(
            ManifestPage(
                doc_id=doc_id,
                path=path,
                route=route,
                canonical_url=url,
                title=title,
                description=description,
                content_hash=c_hash,
                source=SOURCE,
                status=PageStatus.INDEXED,
                tags=["docs", "public"],
            )
        )

    if openapi_spec_path:
        manifest_pages.extend(
            _build_openapi_pages(openapi_spec_path)
        )

    return Manifest(
        source=SOURCE,
        commit_sha=commit_sha,
        namespace=namespace,
        generated_at=datetime.now(timezone.utc).isoformat(),
        pages=manifest_pages,
    )


def _build_openapi_pages(spec_path: str) -> list[ManifestPage]:
    operations = parse_spec(spec_path)
    pages: list[ManifestPage] = []

    for op in operations:
        c_hash = content_hash(op.text)
        pages.append(
            ManifestPage(
                doc_id=op.doc_id,
                path="openapi.yaml",
                route=op.path,
                canonical_url=f"{API_BASE_URL}{op.path}",
                title=op.summary or f"{op.method} {op.path}",
                description=op.description or op.summary,
                content_hash=c_hash,
                source=SOURCE_OPENAPI,
                method=op.method,
                status=PageStatus.INDEXED,
                tags=["openapi", "api", op.tag.lower()] if op.tag else ["openapi", "api"],
            )
        )

    return pages
