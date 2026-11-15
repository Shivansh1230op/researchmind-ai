"""Source exports include current app files and exclude local private data."""
from infra import package_deployment


def test_source_package_excludes_private_env_and_runtime_data(monkeypatch, tmp_path):
    for name in [
        ".env", ".env.local", ".env.vercel.local", ".env.example", ".env.vercel.example",
        "vercel.json", "index.py", "pyproject.toml", "uv.lock",
        "web/.env.local", "web/.env.example", "web/src/page.tsx",
        "web/node_modules/library/index.js", "web/.next-deploy/server.js",
        "docs/screenshots/overview.png", "docs/screenshots/generated.png",
        "data/uploads/private.pdf", "data/documind.db",
        ".vercel/project.json", "venv/private.py", ".venv/private.py",
    ]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    monkeypatch.setattr(package_deployment, "ROOT", tmp_path)
    packaged = {path.relative_to(tmp_path).as_posix() for path in package_deployment.source_files()}
    assert packaged == {
        ".env.example", ".env.vercel.example", "vercel.json", "index.py",
        "pyproject.toml", "uv.lock", "web/.env.example", "web/src/page.tsx",
        "docs/screenshots/overview.png",
    }
