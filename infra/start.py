"""Supervise the private API and public Next.js server in one container."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
API_PORT = 8765  # Must match the API_PROXY_URL used in the Docker build.


def runtime_environment(source: dict[str, str]) -> dict[str, str]:
    """Add the host's public origin without trusting incoming request headers."""
    env = dict(source)
    port = int(env.get("PORT", "3000"))
    if not 1 <= port <= 65535 or port == API_PORT:
        raise ValueError(f"PORT must be 1..65535 and different from private API port {API_PORT}.")
    env["PORT"] = str(port)
    env["HOSTNAME"] = "0.0.0.0"
    env.setdefault("DEBUG", "false")
    env.setdefault("AUTH_REQUIRED", "true")
    origins = [item.strip().rstrip("/") for item in env.get("CORS_ORIGINS", "").split(",") if item.strip()]
    public_url = env.get("PUBLIC_URL") or env.get("RENDER_EXTERNAL_URL")
    if not public_url and env.get("RAILWAY_PUBLIC_DOMAIN"):
        public_url = "https://" + env["RAILWAY_PUBLIC_DOMAIN"]
    if public_url:
        parsed = urlsplit(public_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("PUBLIC_URL must be your site's public http(s) URL.")
        origins.append(f"{parsed.scheme}://{parsed.netloc}")
    env["CORS_ORIGINS"] = ",".join(dict.fromkeys(origins))
    if not origins:
        print("Set PUBLIC_URL or CORS_ORIGINS to your public website origin before using authenticated actions.", flush=True)
    return env


def wait_for_api(process: subprocess.Popen, stopped: threading.Event, timeout: float = 120) -> bool:
    """Only start the web server after the API can answer readiness checks."""
    deadline = time.monotonic() + timeout
    while not stopped.is_set() and time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Python API exited during startup. Check the preceding logs.")
        try:
            with urlopen(f"http://127.0.0.1:{API_PORT}/ready", timeout=2) as response:
                if response.status == 200:
                    return True
        except (URLError, TimeoutError, OSError):
            pass
        stopped.wait(0.25)
    if stopped.is_set():
        return False
    raise RuntimeError("Python API did not become ready within 120 seconds.")


def stop_processes(processes: list[subprocess.Popen]) -> None:
    for process in reversed(processes):
        if process.poll() is None:
            process.terminate()
    deadline = time.monotonic() + 20
    for process in reversed(processes):
        try:
            process.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def main(web_dir: Path | None = None) -> int:
    processes: list[subprocess.Popen] = []
    stopped = threading.Event()
    previous_handlers = {}
    try:
        env = runtime_environment(dict(os.environ))
        web_dir = (web_dir or ROOT / "web").resolve()
        if not (web_dir / "server.js").is_file():
            raise RuntimeError("Next.js standalone server is missing. Build the root Dockerfile first.")
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous_handlers[signum] = signal.signal(signum, lambda *_: stopped.set())
        processes.append(subprocess.Popen([
            sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
            "--port", str(API_PORT), "--workers", "1", "--proxy-headers",
            "--forwarded-allow-ips", "127.0.0.1",
        ], cwd=ROOT, env=env))
        if not wait_for_api(processes[0], stopped):
            return 0
        processes.append(subprocess.Popen(["node", "server.js"], cwd=web_dir, env=env))
        print(f"ResearchMind public server starting on port {env['PORT']}.", flush=True)
        while not stopped.wait(0.5):
            for process in processes:
                code = process.poll()
                if code is not None:
                    print(f"A service exited (code {code}); shutting down the application.", flush=True)
                    return 1
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Deployment startup failed: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        stop_processes(processes)
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--web-dir", type=Path, help="Path to a built Next.js standalone directory")
    raise SystemExit(main(parser.parse_args().web_dir))
