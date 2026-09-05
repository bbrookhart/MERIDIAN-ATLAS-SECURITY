"""SQL text for the two retrieval-time authorization strategies.

These are pure string builders — no DB connection here — so the query
shape itself is unit-testable (assert the WHERE clause is actually present)
independent of a live Postgres. The caller (atlas/db/retrieval.py) owns
the asyncpg pool and executes these.

PRE-FILTER: resolve the caller's permitted `allowed_roles` set first (via
atlas-control), pass it as a hard filter into the vector query itself — the
ANN search only ever ranks candidates the caller is authorized to see.

POST-FILTER: run the vector query unfiltered, over-fetching more than the
final limit to compensate for expected denials, then discard unauthorized
hits after the fact. Cheaper per-query DB work, but can under-deliver
(fewer than `limit` authorized results) when a role's permission set is
narrow relative to the query's real top-k, and its per-request cost is a
function of how many *denied* candidates happened to be nearby — see
packages/atlas-retrieval/README.md's timing-side-channel discussion.
"""

from __future__ import annotations

PREFILTER_SQL = """
SELECT id, title, body, category, owner_role, allowed_roles, source_doc_id, content_sha256
FROM documents
WHERE allowed_roles && $1::text[]
ORDER BY embedding <=> $2
LIMIT $3
"""

POSTFILTER_CANDIDATES_SQL = """
SELECT id, title, body, category, owner_role, allowed_roles, source_doc_id, content_sha256
FROM documents
ORDER BY embedding <=> $1
LIMIT $2
"""

# Post-filter over-fetches this multiple of the requested limit, since some
# fraction of the nearest-by-embedding candidates will be denied and
# discarded after the authorization check.
POSTFILTER_OVERFETCH_MULTIPLIER = 4
