import json
from datetime import UTC, datetime
from pathlib import Path

from atlas.config import settings


async def send_email(to: str, subject: str, body: str, credential: str) -> dict:
    """Simulate sending an email — actually appends to a local JSONL sink.

    No real email is ever sent: this is a synthetic-data lab target with no
    network egress beyond the model endpoint. `credential` is accepted but
    never scope-checked — see credentials.py (WEAKNESS ASI03).
    """
    del credential
    outbox = Path(settings.outbox_dir)
    outbox.mkdir(parents=True, exist_ok=True)
    record = {
        "to": to,
        "subject": subject,
        "body": body,
        "sent_at": datetime.now(UTC).isoformat(),
    }
    with (outbox / "emails.jsonl").open("a") as f:
        f.write(json.dumps(record) + "\n")
    return {"sent": True, "to": to, "subject": subject}
