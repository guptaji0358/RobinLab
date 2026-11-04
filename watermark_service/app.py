"""Watermark service — a small FastAPI app meant to run as a Hugging Face Space.

    GET /download?path=<bucket path>     -> the image, watermarked, as an attachment
    GET /health                          -> {"ok": true}

READ-ONLY: this service only ever GETs from the bucket. It has no upload, delete
or edit code, and nothing is stored — the original is downloaded into memory,
watermarked with Pillow, and streamed back.

Environment (Space -> Settings -> Variables and secrets)
    HF_TOKEN         a fine-grained token with READ access to the bucket only
    WATERMARK_KEY    shared secret; the Cloudflare Function sends it in X-Watermark-Key
    BUCKET_ID        optional, defaults to robinlabdev/robinvault
"""

from __future__ import annotations

import hmac
import os
from urllib.parse import quote

import httpx
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse, Response

from watermark import apply_watermark

BUCKET_ID = os.environ.get("BUCKET_ID", "robinlabdev/robinvault")
HF = "https://huggingface.co"
MAX_SOURCE_BYTES = 40 * 1024 * 1024
ALLOWED_EXT = (".png", ".jpg", ".jpeg", ".webp")
RESERVED_PREFIX = "_thumbs/"  # generated previews, never downloadable

app = FastAPI(title="RobinLab watermark service", docs_url=None, redoc_url=None, openapi_url=None)


def _check_key(provided: str | None) -> None:
    expected = os.environ.get("WATERMARK_KEY", "")
    if not expected:
        raise HTTPException(500, "WATERMARK_KEY is not configured.")
    if not provided or not hmac.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(403, "Forbidden.")


def _fetch_original(path: str) -> bytes:
    """GET one object from the private bucket (read-only)."""
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise HTTPException(500, "HF_TOKEN is not configured.")

    url = f"{HF}/buckets/{BUCKET_ID}/resolve/{quote(path, safe='')}"
    with httpx.Client(timeout=60, follow_redirects=False) as client:
        res = client.get(url, headers={"Authorization": f"Bearer {token}"})
        # Private buckets answer 302 -> signed CDN URL. Follow it WITHOUT the token.
        if 300 <= res.status_code < 400 and res.headers.get("location"):
            res = client.get(res.headers["location"])

    if res.status_code == 404:
        raise HTTPException(404, "No such file in this bucket.")
    if res.status_code != 200:
        raise HTTPException(502, f"Bucket fetch failed (HTTP {res.status_code}).")
    if len(res.content) > MAX_SOURCE_BYTES:
        raise HTTPException(413, "Image is too large to watermark.")
    return res.content


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/download")
def download(
    path: str = Query(..., min_length=1, max_length=512),
    x_watermark_key: str | None = Header(default=None),
) -> Response:
    _check_key(x_watermark_key)

    lowered = path.lower()
    if ".." in path or path.startswith(("/", RESERVED_PREFIX)) or not lowered.endswith(ALLOWED_EXT):
        raise HTTPException(415, "Only bucket images can be downloaded.")

    original = _fetch_original(path)
    try:
        data, fmt = apply_watermark(original)
    except Exception as exc:  # corrupt / unsupported image
        raise HTTPException(422, f"Could not process image: {exc}") from exc

    stem = path.rsplit("/", 1)[-1].rpartition(".")[0]
    filename = f"{stem}-RGS.{ {'JPEG': 'jpg'}.get(fmt, fmt.lower()) }"
    media = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}.get(fmt, "image/png")
    return Response(
        content=data,
        media_type=media,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.exception_handler(HTTPException)
def http_error(_, exc: HTTPException) -> JSONResponse:
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)
