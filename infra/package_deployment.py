"""Create a source archive without local secrets, dependencies, or user data."""
from pathlib import Path
import os
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = {"app", "web", "infra", "migrations", "tests", "docs", ".github"}
FILES = {
    "requirements.txt", "requirements-server.txt", "alembic.ini", "pytest.ini",
    "README.md", ".gitignore", ".env.example", "docs/screenshots/overview.png",
    "pyproject.toml", "uv.lock", "vercel.json", ".vercelignore", "index.py", ".env.vercel.example",
}
SKIP = {"node_modules", "__pycache__", ".pytest_cache", "test-results", "playwright-report", "screenshots"}


def source_files():
    for name in sorted(FILES):
        path = ROOT / name
        if path.is_file() and not path.is_symlink():
            yield path
    for name in sorted(DIRECTORIES):
        for directory, children, files in os.walk(ROOT / name, followlinks=False):
            children[:] = sorted(item for item in children if item not in SKIP
                and not item.startswith(".next") and not (Path(directory) / item).is_symlink())
            for item in sorted(files):
                path = Path(directory) / item
                if path.is_symlink() or item.endswith((".pyc", ".tsbuildinfo")):
                    continue
                if item.startswith(".env") and item not in {".env.example", ".env.vercel.example"}:
                    continue
                yield path


def main():
    output = ROOT / "dist" / "ResearchMind-deploy.zip"
    output.parent.mkdir(exist_ok=True)
    count = 0
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for path in source_files():
            archive.write(path, path.relative_to(ROOT).as_posix())
            count += 1
    print(f"Created {output.name}: {count} source files, {output.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
