from __future__ import annotations

import re

import tiktoken

from .models import ChunkRecord

_ENCODER_NAME = "cl100k_base"
_TARGET_TOKENS = 512
_OVERLAP_TOKENS = 64
_HARD_MAX_TOKENS = 600

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def _count_tokens(text: str, enc: tiktoken.Encoding) -> int:
    return len(enc.encode(text))


def _split_by_headings(text: str) -> list[tuple[str, str]]:
    lines = text.split("\n")
    sections: list[tuple[str, str]] = []
    current_heading = ""
    current_lines: list[str] = []

    for line in lines:
        m = re.match(r"^(#{1,6})\s+(.+)$", line)
        if m:
            if current_lines:
                sections.append((current_heading, "\n".join(current_lines).strip()))
            current_heading = m.group(2).strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_heading, "\n".join(current_lines).strip()))

    return sections


def chunk_text(
    text: str,
    doc_id: str,
    path: str,
    route: str,
    url: str,
    title: str,
    description: str,
    content_hash: str,
    commit_sha: str,
    source: str = "deepidv-docs",
    method: str = "",
) -> list[ChunkRecord]:
    enc = tiktoken.get_encoding(_ENCODER_NAME)
    sections = _split_by_headings(text)

    raw_chunks: list[tuple[str, str]] = []

    for heading, section_text in sections:
        if not section_text.strip():
            continue

        tokens = enc.encode(section_text)

        if len(tokens) <= _HARD_MAX_TOKENS:
            prefix = f"{heading}: " if heading else ""
            raw_chunks.append((heading, section_text))
        else:
            i = 0
            while i < len(tokens):
                end = min(i + _TARGET_TOKENS, len(tokens))
                chunk_tokens = tokens[i:end]
                chunk_text_decoded = enc.decode(chunk_tokens)
                prefix = f"{heading}: " if heading else ""
                raw_chunks.append((heading, chunk_text_decoded.strip()))
                i += _TARGET_TOKENS - _OVERLAP_TOKENS
                if i >= len(tokens):
                    break

    records: list[ChunkRecord] = []
    for idx, (heading, chunk_body) in enumerate(raw_chunks):
        section_prefix = f"{heading}: " if heading else ""
        prefixed = f"{section_prefix}{chunk_body}" if section_prefix else chunk_body
        chunk_id = f"{doc_id}:{idx:04d}"

        records.append(
            ChunkRecord(
                chunk_id=chunk_id,
                doc_id=doc_id,
                path=path,
                route=route,
                url=url,
                title=title,
                description=description,
                content_hash=content_hash,
                commit_sha=commit_sha,
                section=heading,
                chunk_index=idx,
                text=prefixed,
                source=source,
                method=method,
            )
        )

    return records
