from __future__ import annotations

import re

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_IMPORT_RE = re.compile(r"^import\s+.*?(?:from\s+['\"].*?['\"])?;?\s*$", re.MULTILINE)
_EXPORT_CONST_RE = re.compile(
    r"^export\s+const\s+\w+\s*=\s*(?:\([^)]*\)\s*=>|function)\s*[\s\S]*?^[)}];\s*$",
    re.MULTILINE,
)
_JSX_COMPONENT_RE = re.compile(
    r"<(FeatureGrid|FeatureCard|SectionHeader|VideoEmbed|CardGroup|Card|"
    r"Steps|Step|Tip|Warning|Note|Info|CodeGroup|AccordionGroup|Accordion|"
    r"ResponseExample|Icon|Img|img|Image)"
    r"(?:\s[^>]*)?\/?>",
    re.MULTILINE,
)
_JSX_CLOSING_RE = re.compile(
    r"</(FeatureGrid|FeatureCard|SectionHeader|VideoEmbed|CardGroup|Card|"
    r"Steps|Step|Tip|Warning|Note|Info|CodeGroup|AccordionGroup|Accordion|"
    r"ResponseExample|Icon|Img|img|Image)>"
)
_IMAGE_MD_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_HTML_COMMENT_RE = re.compile(r"\{\/\*.*?\*\/\}", re.DOTALL)
_JSX_FRAGMENT_RE = re.compile(r"<>\s*|\s*</>", re.MULTILINE)
_JSX_EXPRESSION_RE = re.compile(r"\{[^}]*\}", re.DOTALL)
_HR_RE = re.compile(r"^\s*---\s*$", re.MULTILINE)
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
_HEADING_TEXT_RE = re.compile(r"^[ \t]*(?:#{1,6})\s+(.+)$", re.MULTILINE)


def extract_frontmatter(text: str) -> tuple[dict[str, str], str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip().strip('"').strip("'")
    body = text[m.end() :]
    return meta, body


def normalize(body: str) -> str:
    text = _EXPORT_CONST_RE.sub("", body)
    text = _IMPORT_RE.sub("", text)
    text = _HTML_COMMENT_RE.sub("", text)
    text = _JSX_FRAGMENT_RE.sub("", text)
    text = _JSX_COMPONENT_RE.sub("", text)
    text = _JSX_CLOSING_RE.sub("", text)
    text = _JSX_EXPRESSION_RE.sub("", text)
    text = _IMAGE_MD_RE.sub("", text)
    text = _HR_RE.sub("", text)
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)
    return text.strip()


def extract_headings(text: str) -> list[str]:
    return [m.group(1).strip() for m in _HEADING_TEXT_RE.finditer(text)]
