from indexer.hashing import content_hash


def test_content_hash_format():
    h = content_hash("hello world")
    assert h.startswith("sha256:")
    assert len(h) == len("sha256:") + 64


def test_content_hash_deterministic():
    h1 = content_hash("test content")
    h2 = content_hash("test content")
    assert h1 == h2


def test_content_hash_differs():
    h1 = content_hash("content a")
    h2 = content_hash("content b")
    assert h1 != h2
