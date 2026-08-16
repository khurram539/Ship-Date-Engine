from __future__ import annotations

import types

import run_server
import run_tests


def test_run_server_uses_fastapi_app(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run(app: str, host: str, port: int, reload: bool) -> None:
        captured.update(app=app, host=host, port=port, reload=reload)

    monkeypatch.setattr(run_server, "build_parser", run_server.build_parser)
    monkeypatch.setitem(__import__("sys").modules, "uvicorn", types.SimpleNamespace(run=fake_run))

    assert run_server.main(["--host", "0.0.0.0", "--port", "9000", "--reload"]) == 0
    assert captured == {
        "app": "ship_date_engine.api:app",
        "host": "0.0.0.0",
        "port": 9000,
        "reload": True,
    }


def test_run_tests_defaults_to_tests_directory(monkeypatch):
    monkeypatch.setattr("pytest.main", lambda args: 0)

    assert run_tests.main([]) == 0
