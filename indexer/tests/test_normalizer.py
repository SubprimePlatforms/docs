from indexer.normalizer import extract_frontmatter, normalize


def test_extract_frontmatter_basic():
    raw = "---\ntitle: Introduction\ndescription: Full-Stack Modular Identity Verification\n---\n\nContent here"
    meta, body = extract_frontmatter(raw)
    assert meta["title"] == "Introduction"
    assert meta["description"] == "Full-Stack Modular Identity Verification"
    assert body.strip() == "Content here"


def test_extract_frontmatter_with_api():
    raw = "---\ntitle: Create Session\ndescription: Create a new session\napi: POST /v1/sessions\n---\n\nBody"
    meta, body = extract_frontmatter(raw)
    assert meta["title"] == "Create Session"
    assert meta["api"] == "POST /v1/sessions"


def test_extract_frontmatter_none():
    raw = "No frontmatter here\nJust content"
    meta, body = extract_frontmatter(raw)
    assert meta == {}
    assert body == raw


def test_normalize_strips_imports():
    body = 'import { Card } from "mintlify"\n\nSome content'
    result = normalize(body)
    assert "import" not in result
    assert "Some content" in result


def test_normalize_strips_export_const():
    body = 'export const VideoEmbed = ({ src }) => (\n  <div>test</div>\n);\n\nReal content'
    result = normalize(body)
    assert "VideoEmbed" not in result
    assert "Real content" in result


def test_normalize_strips_mintlify_components():
    body = '<Tip>\n  Important note\n</Tip>\n\nReal content'
    result = normalize(body)
    assert "Tip" not in result
    assert "Important note" in result
    assert "Real content" in result


def test_normalize_strips_images():
    body = "Some text\n![alt](./img.png)\nMore text"
    result = normalize(body)
    assert "![" not in result
    assert "img.png" not in result
    assert "Some text" in result
    assert "More text" in result


def test_normalize_strips_html_comments():
    body = "Before\n{/* this is a comment */}\nAfter"
    result = normalize(body)
    assert "{/*" not in result
    assert "Before" in result
    assert "After" in result


def test_normalize_strips_feature_cards():
    body = '<FeatureGrid cols={2}>\n  <FeatureCard icon="mask" title="Blind" description="Legacy" />\n</FeatureGrid>\n\n## Heading\n\nContent'
    result = normalize(body)
    assert "FeatureGrid" not in result
    assert "FeatureCard" not in result
    assert "## Heading" in result
    assert "Content" in result


def test_normalize_strips_code_groups():
    body = '<CodeGroup>\n```bash cURL\ncurl -X POST\n```\n</CodeGroup>\n\nAfter'
    result = normalize(body)
    assert "CodeGroup" not in result
    assert "curl" in result
    assert "After" in result


def test_normalize_strips_hr():
    body = "Above\n\n---\n\nBelow"
    result = normalize(body)
    assert "---" not in result
    assert "Above" in result
    assert "Below" in result


def test_normalize_collapses_whitespace():
    body = "A\n\n\n\n\nB"
    result = normalize(body)
    assert "\n\n\n" not in result
