from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


MANIFEST_DOC_ID = "__manifest__"
MANIFEST_CHUNK_ID = "__manifest__:0000"
SOURCE = "deepidv-docs"
SOURCE_OPENAPI = "deepidv-openapi"
DEFAULT_NAMESPACE = "deepidv-docs"
BASE_URL = "https://docs.deepidv.com"
API_BASE_URL = "https://api.deepidv.com"


class PageStatus(str, Enum):
    NEW = "new"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"
    REMOVED = "removed"
    INDEXED = "indexed"


class ManifestPage(BaseModel):
    doc_id: str
    path: str
    route: str
    canonical_url: str
    title: str
    description: str
    content_hash: str
    source: str = SOURCE
    method: str = ""
    status: PageStatus = PageStatus.INDEXED
    chunk_count: int = 0
    tags: list[str] = Field(default_factory=list)


class Manifest(BaseModel):
    schema_version: int = 1
    source: str = "deepidv-docs"
    commit_sha: str = ""
    namespace: str = "deepidv-docs"
    generated_at: str = ""
    pages: list[ManifestPage] = Field(default_factory=list)

    def page_by_doc_id(self, doc_id: str) -> ManifestPage | None:
        for p in self.pages:
            if p.doc_id == doc_id:
                return p
        return None


class ChunkRecord(BaseModel):
    chunk_id: str
    doc_id: str
    path: str
    route: str
    url: str
    title: str
    description: str
    content_hash: str
    commit_sha: str
    section: str
    chunk_index: int
    text: str
    source: str = SOURCE
    method: str = ""


class DiffResult(BaseModel):
    new: list[ManifestPage] = Field(default_factory=list)
    modified: list[ManifestPage] = Field(default_factory=list)
    unchanged: list[ManifestPage] = Field(default_factory=list)
    removed: list[ManifestPage] = Field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.new or self.modified or self.removed)
