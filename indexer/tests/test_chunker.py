from indexer.chunker import chunk_text


def test_chunk_text_small():
    chunks = chunk_text(
        text="Short content here.",
        doc_id="docs:test",
        path="test.mdx",
        route="/test",
        url="https://docs.deepidv.com/test",
        title="Test",
        description="Test page",
        content_hash="sha256:abc",
        commit_sha="abc123",
    )
    assert len(chunks) >= 1
    assert chunks[0].chunk_id == "docs:test:0000"
    assert chunks[0].doc_id == "docs:test"
    assert chunks[0].text == "Short content here."


def test_chunk_text_with_heading():
    chunks = chunk_text(
        text="## Getting Started\n\nFirst step here.",
        doc_id="docs:test",
        path="test.mdx",
        route="/test",
        url="https://docs.deepidv.com/test",
        title="Test",
        description="Test page",
        content_hash="sha256:abc",
        commit_sha="abc123",
    )
    assert len(chunks) >= 1
    assert chunks[0].section == "Getting Started"
    assert "Getting Started: " in chunks[0].text


def test_chunk_text_stable_ids():
    chunks = chunk_text(
        text="Some content\n\n## Section\n\nMore content",
        doc_id="docs:test",
        path="test.mdx",
        route="/test",
        url="https://docs.deepidv.com/test",
        title="Test",
        description="Test page",
        content_hash="sha256:abc",
        commit_sha="abc123",
    )
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_id == f"docs:test:{i:04d}"
        assert chunk.chunk_index == i


def test_chunk_metadata():
    chunks = chunk_text(
        text="Content",
        doc_id="docs:test",
        path="test.mdx",
        route="/test",
        url="https://docs.deepidv.com/test",
        title="My Title",
        description="My Description",
        content_hash="sha256:abc",
        commit_sha="abc123",
    )
    c = chunks[0]
    assert c.title == "My Title"
    assert c.description == "My Description"
    assert c.content_hash == "sha256:abc"
    assert c.commit_sha == "abc123"
    assert c.path == "test.mdx"
    assert c.route == "/test"
    assert c.url == "https://docs.deepidv.com/test"
