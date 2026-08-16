from __future__ import annotations


def main(argv: list[str] | None = None) -> int:
    import pytest

    args = list(argv) if argv is not None else ["tests/"]
    if not args:
        args = ["tests/"]
    return pytest.main(args)


if __name__ == "__main__":
    raise SystemExit(main())
