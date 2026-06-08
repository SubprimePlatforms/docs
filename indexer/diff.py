from __future__ import annotations

from .models import DiffResult, Manifest, ManifestPage, PageStatus


def compute_diff(current: Manifest, previous: Manifest | None) -> DiffResult:
    if previous is None:
        return DiffResult(new=current.pages)

    prev_by_id = {p.doc_id: p for p in previous.pages}
    curr_by_id = {p.doc_id: p for p in current.pages}

    result = DiffResult()

    for page in current.pages:
        prev = prev_by_id.get(page.doc_id)
        if prev is None:
            page.status = PageStatus.NEW
            result.new.append(page)
        elif prev.content_hash != page.content_hash:
            page.status = PageStatus.MODIFIED
            result.modified.append(page)
        else:
            page.status = PageStatus.UNCHANGED
            result.unchanged.append(page)

    for page in previous.pages:
        if page.doc_id not in curr_by_id:
            page.status = PageStatus.REMOVED
            result.removed.append(page)

    return result
