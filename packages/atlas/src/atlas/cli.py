"""Terminal chat client for Atlas.

WEAKNESS (LLM10:2026 — Improper Output Handling): model output is printed to
the terminal verbatim, with no sanitization of ANSI escape sequences or other
control characters. A malicious or injected response can manipulate the
terminal (rewrite the visible prompt, hide text, move the cursor) the moment
it reaches this client. See WEAKNESSES.md.
"""

import sys

import httpx

BASE_URL = "http://127.0.0.1:8000"


def main() -> None:
    role = sys.argv[1] if len(sys.argv) > 1 else "broker"
    print(f"Atlas terminal client — role={role}. Ctrl-D to exit.")
    with httpx.Client(base_url=BASE_URL, headers={"X-Atlas-Role": role}) as client:
        while True:
            try:
                message = input("> ")
            except EOFError:
                break
            resp = client.post("/chat", json={"message": message}, timeout=120)
            resp.raise_for_status()
            print(resp.json()["reply"])


if __name__ == "__main__":
    main()
