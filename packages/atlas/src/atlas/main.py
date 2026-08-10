"""Local (non-Docker) entrypoint. Binds 127.0.0.1 only — never 0.0.0.0."""

import uvicorn


def main() -> None:
    uvicorn.run("atlas.app:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
