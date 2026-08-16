from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Ship Date Engine FastAPI server.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on.")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - exercised via CLI in real use
        raise SystemExit("uvicorn is required to run the API server.") from exc

    try:
        uvicorn.run("ship_date_engine.api:app", host=args.host, port=args.port, reload=args.reload)
    except Exception as exc:
        raise SystemExit(f"Failed to start API server: {exc}") from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
