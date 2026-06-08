import json
from pathlib import Path

import pytest

from indexer.manifest import build_manifest
from indexer.models import SOURCE, SOURCE_OPENAPI


@pytest.fixture
def docs_root(tmp_path):
    (tmp_path / "docs.json").write_text(json.dumps({
        "navigation": {
            "tabs": [{
                "tab": "Test",
                "groups": [{
                    "group": "Test Group",
                    "pages": ["intro"]
                }]
            }]
        }
    }))
    (tmp_path / "intro.mdx").write_text("---\ntitle: Intro\ndescription: Intro page\n---\n\nIntro content")
    return tmp_path


@pytest.fixture
def openapi_spec(tmp_path):
    spec = {
        "openapi": "3.1.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/v1/sessions": {
                "post": {
                    "summary": "Create a session",
                    "description": "Creates a new verification session",
                    "tags": ["Sessions"],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "first_name": {"type": "string", "description": "First name"},
                                        "last_name": {"type": "string", "description": "Last name"},
                                    },
                                    "required": ["first_name", "last_name"],
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Success",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                },
                "get": {
                    "summary": "List sessions",
                    "tags": ["Sessions"],
                    "responses": {
                        "200": {"description": "Success"}
                    },
                },
            }
        },
    }
    spec_path = tmp_path / "openapi.yaml"
    import yaml
    spec_path.write_text(yaml.dump(spec, default_flow_style=False))
    return str(spec_path)


def test_manifest_with_openapi(docs_root, openapi_spec):
    manifest = build_manifest(docs_root, commit_sha="abc", openapi_spec_path=openapi_spec)
    docs_pages = [p for p in manifest.pages if p.source == SOURCE]
    api_pages = [p for p in manifest.pages if p.source == SOURCE_OPENAPI]
    assert len(docs_pages) == 1
    assert len(api_pages) == 2


def test_openapi_page_fields(docs_root, openapi_spec):
    manifest = build_manifest(docs_root, commit_sha="abc", openapi_spec_path=openapi_spec)
    post_page = [p for p in manifest.pages if p.doc_id == "openapi:POST-/v1/sessions"][0]
    assert post_page.source == SOURCE_OPENAPI
    assert post_page.method == "POST"
    assert post_page.path == "openapi.yaml"
    assert post_page.route == "/v1/sessions"
    assert post_page.canonical_url == "https://api.deepidv.com/v1/sessions"
    assert post_page.title == "Create a session"
    assert post_page.content_hash.startswith("sha256:")
    assert "sessions" in post_page.tags


def test_manifest_without_openapi(docs_root):
    manifest = build_manifest(docs_root, commit_sha="abc")
    assert all(p.source == SOURCE for p in manifest.pages)


def test_openapi_pages_have_distinct_hashes(docs_root, openapi_spec):
    manifest = build_manifest(docs_root, commit_sha="abc", openapi_spec_path=openapi_spec)
    api_pages = [p for p in manifest.pages if p.source == SOURCE_OPENAPI]
    hashes = [p.content_hash for p in api_pages]
    assert len(set(hashes)) == len(hashes)
