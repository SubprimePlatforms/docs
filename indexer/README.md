# Docs Indexer

Deterministic, manifest-driven indexing pipeline that keeps a Pinecone vector index in sync with the deepidv docs site.

## Quick start

```bash
pip install -r indexer/requirements.txt

# Set credentials
export PINECONE_API_KEY=...
export PINECONE_INDEX_NAME=...

# Run from the docs project root
python -m indexer.cli --docs-root .
```

The first run performs a full index build. Subsequent runs diff against the stored manifest and only re-index changed pages.

## How it works

```
docs.json ──► Manifest generator ──► Diff engine ──► Embed & upsert ──► Verify
                   │                       │
                   │                       └── Compare content hashes against
                   │                           previous manifest in Pinecone
                   │
                   └── For each page: extract frontmatter, normalize MDX,
                       compute SHA-256 hash
```

1. **Build manifest** — Parse `docs.json` navigation, read each MDX file, normalize content, hash it
2. **Diff** — Fetch the previous manifest from Pinecone, classify pages as new / modified / unchanged / removed
3. **Delete** — Remove stale vectors for modified or removed pages (delete-then-upsert)
4. **Chunk** — Split normalized text into ~512-token chunks with 64-token overlap, prepending the nearest heading
5. **Embed** — Batch embed via Pinecone hosted inference (`llama-text-embed-v2`)
6. **Upsert** — Write vectors to the `deepidv-docs` namespace with full metadata
7. **Verify** — Run semantic queries against the index and assert results contain expected pages
8. **Store manifest** — Persist the updated manifest in Pinecone for the next run

## CLI options

| Flag | Default | Description |
|---|---|---|
| `--docs-root` | `.` | Root directory of the Mintlify docs project |
| `--namespace` | `deepidv-docs` | Pinecone namespace |
| `--api-key` | `PINECONE_API_KEY` env | Pinecone API key |
| `--index-name` | `PINECONE_INDEX_NAME` env | Pinecone index name |
| `--skip-verify` | off | Skip post-index verification queries |

## CI integration

The `.github/workflows/index-docs.yml` workflow runs automatically on merge to `main` when `.mdx`, `docs.json`, or `indexer/` files change. It can also be triggered manually via `workflow_dispatch`.

Required repository secrets:

- `PINECONE_API_KEY`
- `PINECONE_INDEX_NAME`

## Module reference

| Module | Purpose |
|---|---|
| `models.py` | Pydantic models — `Manifest`, `ManifestPage`, `ChunkRecord`, `DiffResult` |
| `normalizer.py` | MDX normalization — strips frontmatter, imports, export const, JSX components, images, HTML comments |
| `hashing.py` | SHA-256 content hashing (`sha256:<hex>`) |
| `manifest.py` | Builds a manifest by parsing `docs.json` and reading each MDX file |
| `diff.py` | Compares current vs previous manifest, classifies pages as new / modified / unchanged / removed |
| `chunker.py` | Token-based chunking (~512 tokens, 64 overlap) with heading context prefixes |
| `embedder.py` | Pinecone hosted inference batch embedding |
| `pinecone_store.py` | Pinecone read/write — manifest storage, delete by `doc_id`, upsert records |
| `verifier.py` | Post-index verification — semantic queries and stale-chunk detection |
| `cli.py` | CLI entry point that orchestrates the full pipeline |

## Vector metadata schema

Each chunk upserted to Pinecone carries:

```json
{
  "source": "deepidv-docs",
  "doc_id": "docs:introduction",
  "chunk_id": "docs:introduction:0003",
  "path": "introduction.mdx",
  "route": "/introduction",
  "url": "https://docs.deepidv.com/introduction",
  "title": "Introduction",
  "description": "Full-Stack Modular Identity Verification",
  "content_hash": "sha256:...",
  "commit_sha": "abc123",
  "section": "Why Traditional Verification Falls Short",
  "chunk_index": 3,
  "text": "..."
}
```

## Manifest schema

The manifest is stored as a single `__manifest__` vector in Pinecone. Its JSON lives in the `manifest_json` metadata field:

```json
{
  "schema_version": 1,
  "source": "deepidv-docs",
  "commit_sha": "abc123",
  "namespace": "deepidv-docs",
  "generated_at": "2026-06-08T12:00:00Z",
  "pages": [
    {
      "doc_id": "docs:introduction",
      "path": "introduction.mdx",
      "route": "/introduction",
      "canonical_url": "https://docs.deepidv.com/introduction",
      "title": "Introduction",
      "description": "Full-Stack Modular Identity Verification",
      "content_hash": "sha256:...",
      "status": "indexed",
      "chunk_count": 8,
      "tags": ["docs", "public"]
    }
  ]
}
```

## Diff behavior

| Change type | Detection | Action |
|---|---|---|
| New page | `doc_id` absent from previous manifest | Embed and upsert |
| Modified page | `content_hash` differs | Delete old vectors by `doc_id`, then re-embed and upsert |
| Unchanged page | `content_hash` matches | Skip |
| Removed page | `doc_id` in previous but not current | Delete all vectors by `doc_id` |

## MDX normalization

The normalizer strips everything that is not semantic content so chunks embed cleanly:

| Strip / flatten | Example |
|---|---|
| YAML frontmatter | `---\ntitle: ...\n---` |
| Import / export statements | `import { ... } from "..."` |
| JSX component definitions | `export const VideoEmbed = ...` |
| Mintlify UI wrappers | `<Note>`, `<Warning>`, `<Steps>` — inner text kept, tags discarded |
| Image references | `![alt](./img.png)` |
| HTML comments | `{/* ... */}` |

## Running tests

```bash
pip install pytest
python -m pytest indexer/tests/ -v
```
