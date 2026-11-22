"""POST /api/canva/edit: upload a logo to Canva and create a design from it."""

import base64
import json
import re
import time

from .canva_config import CANVA_API
from .canva_http import canva_call
from .canva_sessions import canva_session
from .hf_stream import open_file_stream
from .listing import get_listing
from .responses import send_json


def _clamp(n) -> int:
    try:
        return min(8000, max(40, int(n)))
    except (TypeError, ValueError):
        return 1000


def canva_edit(h) -> None:
    length = int(h.headers.get("Content-Length") or 0)
    try:
        body = json.loads(h.rfile.read(length) or b"{}")
    except ValueError:
        body = {}
    path = str(body.get("path", ""))
    if not path.startswith("LOGO/"):
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

    title = (str(body.get("title", "")).strip() or re.sub(r"\.[^.]+$", "", entry["name"]))[:255]
    auth = {"Authorization": f"Bearer {sess['a']}"}
    conn, resp = open_file_stream(h.token, path)
    try:
        data = resp.read()
    finally:
        conn.close()

    meta = json.dumps({"name_base64": base64.b64encode(title.encode()).decode()})
    status, res = canva_call(
        "POST", f"{CANVA_API}/asset-uploads",
        {**auth, "Content-Type": "application/octet-stream", "Asset-Upload-Metadata": meta}, data,
    )
    if status in (401, 403):
        send_json(h, {"error": "auth_required", "message": "Canva sign-in expired."}, 401)
        return
    job = res.get("job")
    for _ in range(20):
        if not job or job.get("status") != "in_progress":
            break
        time.sleep(0.6)
        job = canva_call("GET", f"{CANVA_API}/asset-uploads/{job['id']}", auth)[1].get("job", job)
    if not job or job.get("status") != "success":
        send_json(h, {"error": "upstream_error", "message": "Canva could not import the image."}, 502)
        return

    status, made = canva_call("POST", f"{CANVA_API}/designs", {**auth, "Content-Type": "application/json"}, json.dumps({
        "design_type": {"type": "custom", "width": _clamp(body.get("w")), "height": _clamp(body.get("h"))},
        "asset_id": job["asset"]["id"], "title": title,
    }).encode())
    edit_url = (made.get("design") or {}).get("urls", {}).get("edit_url")
    if status != 200 or not edit_url:
        send_json(h, {"error": "upstream_error", "message": "Canva could not create the design."}, 502)
        return
    send_json(h, {"editUrl": edit_url, "title": title})
