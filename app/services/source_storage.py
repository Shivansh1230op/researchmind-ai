"""Private cloud source files with bounded, request-local extraction copies."""
from contextlib import contextmanager
from pathlib import Path
import tempfile
import uuid

from app.core.config import get_settings


def is_blob(path):
    return path.startswith("blob:")


def blob_client():
    from vercel.blob import sync
    return sync


def save_source(content, file_type):
    settings = get_settings()
    if settings.storage_backend == "vercel_blob":
        pathname = f"sources/{uuid.uuid4().hex}.{file_type}"
        uploaded = blob_client().put_blob(pathname, content, access="private")
        return "blob:" + uploaded.pathname
    path = Path(settings.upload_dir) / f"{uuid.uuid4().hex}.{file_type}"
    path.write_bytes(content)
    return str(path)


def delete_source(path):
    if is_blob(path):
        blob_client().delete_blob(path[5:])
    else:
        Path(path).unlink(missing_ok=True)


@contextmanager
def local_source(path, file_type):
    if not is_blob(path):
        yield path
        return
    limit = get_settings().max_file_size_bytes
    # The directory is private and unique to this invocation, even on warm hosts.
    with tempfile.TemporaryDirectory(prefix="researchmind-") as directory:
        local = Path(directory) / f"source.{file_type}"
        size = 0
        with blob_client().stream_blob(path[5:], access="private") as stream, local.open("wb") as output:
            for chunk in stream:
                size += len(chunk)
                if size > limit:
                    raise ValueError("Source exceeds the configured size limit")
                output.write(chunk)
        validate_content(local.read_bytes(), file_type)
        yield str(local)


def validate_content(content, file_type):
    """Validate original bytes before any file parser sees them."""
    if not content:
        raise ValueError("The document is empty.")
    if file_type == "pdf" and not content.startswith(b"%PDF-"):
        raise ValueError("File is not a valid PDF.")
    if file_type == "docx":
        import io
        import zipfile
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                if "word/document.xml" not in archive.namelist() or sum(i.file_size for i in archive.infolist()) > get_settings().max_file_size_bytes * 10:
                    raise ValueError()
        except (zipfile.BadZipFile, ValueError):
            raise ValueError("File is not a valid DOCX or is too large when expanded.") from None
    if file_type in {"txt", "md"} and b"\x00" in content:
        raise ValueError("Text files must not contain binary content.")
