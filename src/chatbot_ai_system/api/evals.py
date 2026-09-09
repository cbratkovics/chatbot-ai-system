"""Serve the committed system-eval artifact (ADR 0006).

``GET /api/v1/evals/latest`` returns ``evals/results/latest.json`` as written by
``python -m evals.run``. It is a static file: an ETag lets the UI revalidate cheaply, and a
missing file is a 404 in the standard error envelope rather than an empty object, so the
frontend can fall back to its build-time copy and say which source it is showing.
"""

import hashlib
from email.utils import formatdate
from pathlib import Path

from fastapi import APIRouter, Depends, Request, Response, status

from ..config import Settings, get_settings
from .errors import error_response

router = APIRouter(prefix="/evals", tags=["evals"])

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESULTS_PATH = REPO_ROOT / "evals" / "results" / "latest.json"


def results_path(settings: Settings) -> Path:
    return (
        Path(settings.evals_results_path) if settings.evals_results_path else DEFAULT_RESULTS_PATH
    )


@router.get("/latest")
async def latest_results(request: Request, settings: Settings = Depends(get_settings)) -> Response:
    """The most recent committed eval run, with ETag / If-None-Match support."""
    path = results_path(settings)
    request_id = getattr(request.state, "request_id", None)
    if not path.is_file():
        return error_response(
            status.HTTP_404_NOT_FOUND,
            "evals_not_found",
            f"No eval results at {path.name}; run `make evals` and commit the artifact",
            request_id=request_id,
        )
    body = path.read_bytes()
    etag = f'"{hashlib.sha256(body).hexdigest()[:32]}"'
    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=300",
        "Last-Modified": formatdate(path.stat().st_mtime, usegmt=True),
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
    return Response(content=body, media_type="application/json", headers=headers)
