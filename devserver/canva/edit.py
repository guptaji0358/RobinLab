"""POST /api/canva/edit: upload a logo to Canva and create a design from it.

Mirrors handleEdit in scripts/functions/api/canva/[[path]].js: keep them in sync.
"""

import base64
import json
import math
import re
import time

from devserver.canva.config import CANVA_API
from devserver.canva.client import canva_call
from devserver.canva.sessions import canva_session
from devserver.hf.stream import open_file_stream
from devserver.hf.listing import get_listing
from devserver.web.responses import send_json

DEFAULT_DIM = 1000
MIN_DIM = 40
MAX_DIM = 8000
MAX_AREA = 25_000_000
MAX_ASSET_NAME = 50
MAX_TITLE = 255
MAX_UPLOAD_BYTES = 30 * 1024 * 1024
POLL_TRIES = 20
POLL_SECONDS = 0.6


def _dim(n) -> int:
    if isinstance(n, bool) or not isinstance(n, (int, float, str)):
        return DEFAULT_DIM
    if isinstance(n, str) and not n.strip():
        return DEFAULT_DIM
    try:
        v = float(n)
    except ValueError:
        return DEFAULT_DIM
    if not math.isfinite(v) or v <= 0:
        return DEFAULT_DIM
    return min(MAX_DIM, max(MIN_DIM, int(math.floor(v + 0.5))))


def fit_design(w, h) -> tuple[int, int]:
    """Integers inside Canva's 40..8000 px and 25 MP limits, aspect ratio kept."""
    width, height = _dim(w), _dim(h)
    if width * height > MAX_AREA:
        k = math.sqrt(MAX_AREA / (width * height))
        width = max(MIN_DIM, math.floor(width * k))
        height = max(MIN_DIM, math.floor(height * k))
    return width, height


def asset_name(title: str) -> str:
    return str(title)[:MAX_ASSET_NAME]  # Python str slices by code point


def _auth_expired(h) -> None:
    send_json(h, {"error": "auth_required", "message": "Canva sign-in expired."}, 401)


def canva_edit(h) -> None:
    origin = h.headers.get("Origin")
    host = h.headers.get("Host") or ""
    if h.headers.get("Sec-Fetch-Site") == "cross-site" or (origin and origin.split("://", 1)[-1] != host):
        send_json(h, {"error": "forbidden"}, 403)
        return
    length = int(h.headers.get("Content-Length") or 0)
    try:
        body = json.loads(h.rfile.read(length) or b"{}")
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    path = str(body.get("path", ""))
    if not path.startswith("LOGO/") or ".." in path or "\\" in path:
        send_json(h, {"error": "bad_path", "message": "Only logos can be opened in Canva."}, 400)
        return
    sess = canva_session(h)
    if not sess:
        send_json(h, {"error": "auth_required", "message": "Sign in to Canva first."}, 401)
        return
    entry = next((f for f in get_listing(h.token)["files"] if f["path"] == path), None)
    if not entry or not entry.get("previewable"):
        send_json(h, {"error": "not_found", "message": "No such logo."}, 404)
        return

    title = (str(body.get("title", "")).strip() or re.sub(r"\.[^.]+$", "", entry["name"]))[:MAX_TITLE]
    auth = {"Authorization": f"Bearer {sess['a']}"}
    conn, resp = open_file_stream(h.token, path)
    try:
        data = resp.read(MAX_UPLOAD_BYTES + 1)
    finally:
        conn.close()
    if len(data) > MAX_UPLOAD_BYTES:
        send_json(h, {"error": "too_large", "message": "That image is too large for Canva import."}, 413)
        return

    meta = json.dumps({"name_base64": base64.b64encode(asset_name(title).encode()).decode()})
    status, res = canva_call(
        "POST", f"{CANVA_API}/asset-uploads",
        {**auth, "Content-Type": "application/octet-stream", "Asset-Upload-Metadata": meta}, data,
    )
    if status in (401, 403):
        _auth_expired(h)
        return
    if status == 429:
        send_json(h, {"error": "rate_limited", "message": "Canva is rate limiting requests. Try again in a minute."}, 429)
        return
    job = res.get("job")
    if not job:
        send_json(h, {"error": "upstream_error", "message": "Canva refused the upload."}, 502)
        return

    for _ in range(POLL_TRIES):
        if job.get("status") != "in_progress":
            break
        time.sleep(POLL_SECONDS)
        pstatus, pres = canva_call("GET", f"{CANVA_API}/asset-uploads/{job['id']}", auth)
        if pstatus in (401, 403):
            _auth_expired(h)
            return
        if pstatus == 429 or pstatus >= 500:
            continue
        if pstatus != 200:
            send_json(h, {"error": "upstream_error", "message": f"Canva could not check the import (HTTP {pstatus})."}, 502)
            return
        job = pres.get("job", job)
    if job.get("status") == "in_progress":
        send_json(h, {"error": "timeout", "message": "Canva is still importing the image. Try again shortly."}, 504)
        return
    if job.get("status") != "success" or not (job.get("asset") or {}).get("id"):
        why = (job.get("error") or {}).get("message")
        send_json(h, {"error": "upstream_error", "message": f"Canva could not import the image: {why}" if why else "Canva could not import the image."}, 502)
        return

    width, height = fit_design(body.get("w"), body.get("h"))
    status, made = canva_call("POST", f"{CANVA_API}/designs", {**auth, "Content-Type": "application/json"}, json.dumps({
        "design_type": {"type": "custom", "width": width, "height": height},
        "asset_id": job["asset"]["id"], "title": title,
    }).encode())
    if status in (401, 403):
        _auth_expired(h)
        return
    if status == 429:
        send_json(h, {"error": "rate_limited", "message": "Canva is rate limiting requests. Try again in a minute."}, 429)
        return
    edit_url = (made.get("design") or {}).get("urls", {}).get("edit_url")
    if status != 200 or not edit_url:
        send_json(h, {"error": "upstream_error", "message": "Canva could not create the design."}, 502)
        return
    send_json(h, {"editUrl": edit_url, "title": title})
