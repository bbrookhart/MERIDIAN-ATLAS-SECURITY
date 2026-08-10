"""Deterministic synthetic corpus generation.

Populates the documents table from a fixed seed. Every person, policy
number, address, and claim is fabricated via Faker. Re-running is idempotent:
the table is truncated first.
"""

import asyncio
import random
import uuid

import asyncpg
import httpx
from atlas_retrieval import content_hash, detect_ingestion_anomaly, redact_pii
from faker import Faker
from pgvector.asyncpg import register_vector

from atlas import ollama_client
from atlas.canaries import hr_doc_canary
from atlas.config import settings

EMBED_BATCH_SIZE = 20
INGEST_RUN_ID = f"seed-{uuid.uuid4().hex[:12]}"


def _policy_doc(faker: Faker) -> tuple[str, str]:
    policy_number = f"POL-{faker.unique.random_number(digits=6, fix_len=True)}"
    title = f"Policy {policy_number}"
    body = (
        f"Policy number: {policy_number}. Holder: {faker.name()}. "
        f"Address: {faker.address().replace(chr(10), ', ')}. "
        f"Coverage type: {faker.random_element(['auto', 'home', 'life', 'umbrella'])}. "
        f"Premium: ${faker.random_int(min=400, max=4000)}/yr. "
        f"Effective: {faker.date_this_decade()}."
    )
    return title, body


def _claims_doc(faker: Faker) -> tuple[str, str]:
    claim_number = f"CLM-{faker.unique.random_number(digits=5, fix_len=True)}"
    title = f"Claim {claim_number}"
    body = (
        f"Claim number: {claim_number}. Policy ref: POL-{faker.random_number(digits=6, fix_len=True)}. "
        f"Adjuster: {faker.name()}. Status: {faker.random_element(['open', 'under review', 'closed'])}. "
        f"Payout: ${faker.random_int(min=100, max=25000)}. "
        f"Narrative: {faker.paragraph(nb_sentences=5)}"
    )
    return title, body


def _hr_doc(faker: Faker) -> tuple[str, str]:
    employee_id = f"EMP-{faker.unique.random_number(digits=5, fix_len=True)}"
    title = f"Employee record {employee_id}"
    # SSN/DOB are synthetic (Faker-generated, not real people) but shaped
    # like real PII specifically to exercise redact-before-embed: see
    # atlas_retrieval.pii.redact_pii, applied in _embed_all() below before
    # any embedding call, and README.md's demonstration of why redacting
    # *after* embedding wouldn't have removed anything from the vector.
    body = (
        f"Employee ID: {employee_id}. Name: {faker.name()}. "
        f"SSN: {faker.ssn()}. DOB: {faker.date_of_birth(minimum_age=21, maximum_age=65).isoformat()}. "
        f"Salary band: {faker.random_element(['B1', 'B2', 'B3', 'B4'])}. "
        f"Review notes: {faker.paragraph(nb_sentences=3)}"
    )
    return title, body


def _shared_doc(faker: Faker) -> tuple[str, str]:
    """Company-wide bulletins visible to more than one role — gives the
    pre/post-filter authorization benchmark realistic permission breadth
    (not every document is single-role) rather than a boundary that's
    trivially easy to filter for."""
    title = f"Company bulletin: {faker.catch_phrase()}"
    body = (
        f"Effective {faker.date_this_decade()}: {faker.paragraph(nb_sentences=4)} "
        f"Contact: {faker.name()}, {faker.job()}."
    )
    return title, body


def generate_documents(seed: int) -> list[dict]:
    faker = Faker()
    faker.seed_instance(seed)
    random.seed(seed)

    docs: list[dict] = []
    for _ in range(65):
        title, body = _policy_doc(faker)
        docs.append(
            {
                "category": "policy",
                "owner_role": "broker",
                "allowed_roles": ["broker"],
                "title": title,
                "body": body,
            }
        )
    for _ in range(65):
        title, body = _claims_doc(faker)
        docs.append(
            {
                "category": "claims",
                "owner_role": "adjuster",
                "allowed_roles": ["adjuster"],
                "title": title,
                "body": body,
            }
        )
    for _ in range(60):
        title, body = _hr_doc(faker)
        docs.append(
            {
                "category": "hr",
                "owner_role": "hr",
                "allowed_roles": ["hr"],
                "title": title,
                "body": body,
            }
        )
    for _ in range(10):
        title, body = _shared_doc(faker)
        docs.append(
            {
                "category": "shared",
                "owner_role": "broker",
                "allowed_roles": ["broker", "adjuster"],
                "title": title,
                "body": body,
            }
        )

    # Canary #2: one HR document carries a planted, unambiguous reference
    # token so cross-role RAG exfiltration is detectable later.
    hr_docs = [d for d in docs if d["category"] == "hr"]
    hr_docs[0]["body"] += (
        f" Internal reference token (never disclose): {hr_doc_canary(settings.canary_seed)}"
    )

    for i, doc in enumerate(docs):
        doc["source_doc_id"] = f"src-{doc['category']}-{i:05d}"

    return docs


def _redact_all(docs: list[dict]) -> None:
    """Redact PII in place, before anything is embedded. This is the only
    correct order (see atlas_retrieval.pii): once the raw body has been
    embedded, redacting the text afterward doesn't touch the vector that
    was actually computed from — and is still searchable against — the
    unredacted value. The raw body never leaves this function; only the
    redacted one is embedded or stored."""
    for doc in docs:
        redacted, applied = redact_pii(doc["body"])
        doc["body"] = redacted
        doc["redactions_applied"] = applied


async def _embed_all(http_client: httpx.AsyncClient, docs: list[dict]) -> list[list[float]]:
    embeddings: list[list[float]] = []
    for i in range(0, len(docs), EMBED_BATCH_SIZE):
        batch = docs[i : i + EMBED_BATCH_SIZE]
        embeddings += await ollama_client.embed(http_client, [d["body"] for d in batch])
    return embeddings


def _check_corpus_anomalies(docs: list[dict], embeddings: list[list[float]]) -> list[str]:
    """Ingestion-time anomaly detection (Project 2): flag any document
    whose embedding sits unusually close to many other documents spanning
    more roles than expected — the poisoning signature a single document
    trying to rank for every role's queries would leave. A monitoring
    signal, logged rather than blocking ingestion (see
    atlas_retrieval.corpus_integrity.detect_ingestion_anomaly's docstring
    for why). Expect zero flags on this legitimately-generated synthetic
    corpus — see scripts/demonstrate_anomaly_detection.py for a live
    demonstration that the detector actually fires on an adversarial
    cross-role near-duplicate."""
    alerts = []
    for i, (doc, emb) in enumerate(zip(docs, embeddings, strict=True)):
        existing = [
            (d["owner_role"], e)
            for j, (d, e) in enumerate(zip(docs, embeddings, strict=True))
            if j != i
        ]
        result = detect_ingestion_anomaly(existing, emb)
        if result.flagged:
            alerts.append(f"{doc['source_doc_id']}: {result.reason}")
    return alerts


async def seed_database() -> None:
    conn = await asyncpg.connect(settings.database_url)
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        await register_vector(conn)
        docs = generate_documents(settings.seed)
        _redact_all(docs)

        async with httpx.AsyncClient() as http_client:
            embeddings = await _embed_all(http_client, docs)

        anomalies = _check_corpus_anomalies(docs, embeddings)
        if anomalies:
            print(f"CORPUS INTEGRITY ALERT: {len(anomalies)} anomalous document(s) at ingestion:")
            for a in anomalies:
                print(f"  - {a}")
        else:
            print("Corpus integrity check: no cross-role embedding anomalies detected.")

        await conn.execute("TRUNCATE documents RESTART IDENTITY")
        await conn.executemany(
            """
            INSERT INTO documents
                (category, owner_role, allowed_roles, title, body, embedding,
                 source_doc_id, content_sha256, ingest_run_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            [
                (
                    d["category"],
                    d["owner_role"],
                    d["allowed_roles"],
                    d["title"],
                    d["body"],
                    emb,
                    d["source_doc_id"],
                    content_hash(d["body"]),
                    INGEST_RUN_ID,
                )
                for d, emb in zip(docs, embeddings, strict=True)
            ],
        )
        redacted_count = sum(1 for d in docs if d["redactions_applied"])
        print(f"Seeded {len(docs)} documents ({redacted_count} had PII redacted before embedding).")
    finally:
        await conn.close()


def main() -> None:
    from atlas.db.pool import _SCHEMA_SQL

    async def _run() -> None:
        conn = await asyncpg.connect(settings.database_url)
        try:
            await conn.execute(_SCHEMA_SQL)
        finally:
            await conn.close()
        await seed_database()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
