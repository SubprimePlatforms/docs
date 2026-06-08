from indexer.diff import compute_diff
from indexer.models import Manifest, ManifestPage, PageStatus


def _make_page(doc_id: str, content_hash: str = "sha256:abc") -> ManifestPage:
    return ManifestPage(
        doc_id=doc_id,
        path=f"{doc_id.replace('docs:', '')}.mdx",
        route=f"/{doc_id.replace('docs:', '')}",
        canonical_url=f"https://docs.deepidv.com/{doc_id.replace('docs:', '')}",
        title="Test",
        description="Test",
        content_hash=content_hash,
    )


def test_diff_no_previous():
    current = Manifest(pages=[_make_page("docs:a"), _make_page("docs:b")])
    diff = compute_diff(current, None)
    assert len(diff.new) == 2
    assert len(diff.modified) == 0
    assert len(diff.unchanged) == 0
    assert len(diff.removed) == 0


def test_diff_unchanged():
    current = Manifest(pages=[_make_page("docs:a", "sha256:1")])
    previous = Manifest(pages=[_make_page("docs:a", "sha256:1")])
    diff = compute_diff(current, previous)
    assert len(diff.unchanged) == 1
    assert diff.unchanged[0].status == PageStatus.UNCHANGED


def test_diff_modified():
    current = Manifest(pages=[_make_page("docs:a", "sha256:2")])
    previous = Manifest(pages=[_make_page("docs:a", "sha256:1")])
    diff = compute_diff(current, previous)
    assert len(diff.modified) == 1
    assert diff.modified[0].status == PageStatus.MODIFIED


def test_diff_removed():
    current = Manifest(pages=[])
    previous = Manifest(pages=[_make_page("docs:a")])
    diff = compute_diff(current, previous)
    assert len(diff.removed) == 1
    assert diff.removed[0].status == PageStatus.REMOVED


def test_diff_mixed():
    current = Manifest(pages=[
        _make_page("docs:a", "sha256:1"),
        _make_page("docs:b", "sha256:new"),
        _make_page("docs:c", "sha256:1"),
    ])
    previous = Manifest(pages=[
        _make_page("docs:a", "sha256:1"),
        _make_page("docs:b", "sha256:old"),
        _make_page("docs:d", "sha256:1"),
    ])
    diff = compute_diff(current, previous)
    assert len(diff.unchanged) == 1
    assert len(diff.modified) == 1
    assert len(diff.new) == 1
    assert len(diff.removed) == 1
    assert diff.has_changes is True


def test_diff_no_changes():
    current = Manifest(pages=[_make_page("docs:a", "sha256:1")])
    previous = Manifest(pages=[_make_page("docs:a", "sha256:1")])
    diff = compute_diff(current, previous)
    assert diff.has_changes is False
