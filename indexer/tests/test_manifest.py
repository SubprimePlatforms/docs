from indexer.manifest import build_manifest
from indexer.models import Manifest
from pathlib import Path
import json
import pytest


@pytest.fixture
def docs_root(tmp_path):
    (tmp_path / "docs.json").write_text(json.dumps({
        "navigation": {
            "tabs": [{
                "tab": "Test",
                "groups": [{
                    "group": "Test Group",
                    "pages": ["intro", "guide"]
                }]
            }]
        }
    }))
    (tmp_path / "intro.mdx").write_text("---\ntitle: Intro\ndescription: Intro page\n---\n\nIntro content")
    (tmp_path / "guide.mdx").write_text("---\ntitle: Guide\ndescription: Guide page\n---\n\nGuide content")
    return tmp_path


def test_build_manifest_pages(docs_root):
    manifest = build_manifest(docs_root, commit_sha="abc123")
    assert len(manifest.pages) == 2
    assert manifest.pages[0].doc_id == "docs:intro"
    assert manifest.pages[1].doc_id == "docs:guide"


def test_build_manifest_metadata(docs_root):
    manifest = build_manifest(docs_root, commit_sha="abc123")
    assert manifest.commit_sha == "abc123"
    assert manifest.source == "deepidv-docs"
    assert manifest.namespace == "deepidv-docs"
    assert manifest.generated_at != ""


def test_build_manifest_page_fields(docs_root):
    manifest = build_manifest(docs_root, commit_sha="abc123")
    page = manifest.pages[0]
    assert page.title == "Intro"
    assert page.description == "Intro page"
    assert page.path == "intro.mdx"
    assert page.route == "/intro"
    assert page.canonical_url == "https://docs.deepidv.com/intro"
    assert page.content_hash.startswith("sha256:")


def test_build_manifest_skips_missing(docs_root):
    (tmp_not_exist := docs_root / "nonexistent.mdx")
    docs_json = docs_root / "docs.json"
    data = json.loads(docs_json.read_text())
    data["navigation"]["tabs"][0]["groups"][0]["pages"].append("nonexistent")
    docs_json.write_text(json.dumps(data))
    manifest = build_manifest(docs_root, commit_sha="abc123")
    assert len(manifest.pages) == 2
