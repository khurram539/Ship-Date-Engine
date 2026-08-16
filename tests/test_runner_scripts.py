from __future__ import annotations

import types

import run_server
import run_tests


def test_run_server_uses_fastapi_app(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run(app: str, host: str, port: int, reload: bool) -> None:
        captured.update(app=app, host=host, port=port, reload=reload)

    monkeypatch.setitem(__import__("sys").modules, "uvicorn", types.SimpleNamespace(run=fake_run))

    assert run_server.main(["--host", "0.0.0.0", "--port", "9000", "--reload"]) == 0
    assert captured == {
        "app": "ship_date_engine.api:app",
        "host": "0.0.0.0",
        "port": 9000,
        "reload": True,
    }


def test_run_server_exits_cleanly_on_startup_failure(monkeypatch):
    def fake_run(app: str, host: str, port: int, reload: bool) -> None:
        raise OSError("port already in use")

    monkeypatch.setitem(__import__("sys").modules, "uvicorn", types.SimpleNamespace(run=fake_run))

    try:
        run_server.main(["--port", "9000"])
    except SystemExit as exc:
        assert str(exc) == "Failed to start API server: port already in use"
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("Expected SystemExit")


def test_run_tests_defaults_to_tests_directory(monkeypatch):
    captured: dict[str, object] = {}

    def fake_pytest_main(args):
        captured["args"] = args
        return 0

    monkeypatch.setattr("pytest.main", fake_pytest_main)

    assert run_tests.main([]) == 0
    assert captured == {"args": ["tests/"]}
