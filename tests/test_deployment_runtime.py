"""Deployment lifecycle and public-origin handling without model/provider calls."""
import signal
import subprocess
import threading
from unittest.mock import Mock

import pytest

from infra import start
from infra import package_deployment


@pytest.mark.parametrize("source,expected", [
    ({"RENDER_EXTERNAL_URL": "https://research.onrender.com"}, "https://research.onrender.com"),
    ({"RAILWAY_PUBLIC_DOMAIN": "research.up.railway.app"}, "https://research.up.railway.app"),
    ({"PUBLIC_URL": "https://research.example.com/", "RENDER_EXTERNAL_URL": "https://other.example.com"}, "https://research.example.com"),
])
def test_platform_origin_allows_cookie_mutations(source, expected):
    env = start.runtime_environment({**source, "PORT": "10000"})
    assert expected in env["CORS_ORIGINS"].split(",")
    assert env["PORT"] == "10000"
    assert env["HOSTNAME"] == "0.0.0.0"


def test_custom_domain_preserves_explicit_origins():
    source = {"PUBLIC_URL": "https://research.example.com", "CORS_ORIGINS": " https://preview.example.com/,https://research.example.com "}
    env = start.runtime_environment(source)
    assert env["CORS_ORIGINS"] == "https://preview.example.com,https://research.example.com"
    assert source["PUBLIC_URL"] == "https://research.example.com"


@pytest.mark.parametrize("port", ["0", "70000", "invalid", str(start.API_PORT)])
def test_invalid_or_conflicting_port_fails_before_starting_children(port):
    with pytest.raises(ValueError):
        start.runtime_environment({"PORT": port})


@pytest.mark.parametrize("url", ["example.com", "https://", "https://user:password@example.com", "file:///data"])
def test_invalid_public_origin_is_rejected(url):
    with pytest.raises(ValueError):
        start.runtime_environment({"PUBLIC_URL": url})


def test_failed_api_does_not_leave_startup_waiting():
    process = Mock()
    process.poll.return_value = 1
    with pytest.raises(RuntimeError, match="exited during startup"):
        start.wait_for_api(process, threading.Event())


def test_shutdown_cancels_readiness_wait():
    stopped = threading.Event()
    stopped.set()
    assert start.wait_for_api(Mock(), stopped) is False


def test_cleanup_kills_and_reaps_a_stuck_child():
    process = Mock()
    process.poll.return_value = None
    process.wait.side_effect = [subprocess.TimeoutExpired("child", 0), 0]
    start.stop_processes([process])
    process.terminate.assert_called_once()
    process.kill.assert_called_once()
    assert process.wait.call_count == 2


def test_web_failure_shuts_down_api_and_returns_failure(monkeypatch, tmp_path):
    (tmp_path / "server.js").write_text("// test artifact")
    api, web = Mock(), Mock()
    api.poll.return_value = None
    web.poll.return_value = 2
    monkeypatch.setattr(start.subprocess, "Popen", Mock(side_effect=[api, web]))
    monkeypatch.setattr(start, "wait_for_api", lambda *_: True)
    monkeypatch.setenv("PUBLIC_URL", "https://research.example.com")
    monkeypatch.setenv("PORT", "10000")
    original_handler = signal.getsignal(signal.SIGTERM)
    assert start.main(tmp_path) == 1
    api.terminate.assert_called_once()
    api.wait.assert_called_once()
    web.wait.assert_called_once()
    assert signal.getsignal(signal.SIGTERM) == original_handler


def test_source_package_excludes_private_env_and_runtime_data(monkeypatch, tmp_path):
    for name in [".env", ".env.production", ".env.example", ".env.production.example",
                 "Dockerfile", "web/.env.local", "web/.env.example", "web/src/page.tsx",
                 "web/node_modules/library/index.js", "web/.next-deploy/server.js",
                 "data/uploads/private.pdf", "data/documind.db",
                 ".streamlit/credentials.toml", "venv/private.py"]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    monkeypatch.setattr(package_deployment, "ROOT", tmp_path)
    packaged = {path.relative_to(tmp_path).as_posix() for path in package_deployment.source_files()}
    assert packaged == {"Dockerfile", ".env.example", ".env.production.example",
                        "web/.env.example", "web/src/page.tsx"}
