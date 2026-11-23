"""/api/collection/skills and /api/collection/skill."""

import re
import urllib.parse

from devserver.core.config import SKILLS_FOLDER
from devserver.hf.stream import open_file_stream
from devserver.hf.listing import get_listing
from devserver.web.responses import send_json
from devserver.skills.ids import skill_id
from devserver.skills.store import get_skills


def serve_skills_list(h) -> None:
    try:
        skills = get_skills(h.token)
    except Exception as err:  # noqa: BLE001
        send_json(h, {"error": "upstream_error", "message": str(err)}, 502)
    else:
        send_json(h, {"count": len(skills), "skills": skills})


def serve_skill(h, parsed: urllib.parse.SplitResult) -> None:
    query = urllib.parse.parse_qs(parsed.query)
    sid = (query.get("id") or [""])[0]
    if not re.fullmatch(r"[a-z0-9-]{1,100}", sid):
        send_json(h, {"error": "bad_request"}, 400)
        return
    try:
        entry = next(
            (e for e in get_listing(h.token)["files"]  # type: ignore[union-attr]
             if e["folder"] == SKILLS_FOLDER and e["name"].lower().endswith(".md") and skill_id(e["name"]) == sid),
            None,
        )
        if entry is None:
            send_json(h, {"error": "not_found"}, 404)
            return
        conn, resp = open_file_stream(h.token, entry["path"])
        try:
            if resp.status != 200:
                raise RuntimeError(f"Skill fetch failed (HTTP {resp.status})")
            body = resp.read()
        finally:
            conn.close()
    except Exception as err:  # noqa: BLE001
        send_json(h, {"error": "upstream_error", "message": str(err)}, 502)
        return
    h.send_response(200)
    h.send_header("Content-Type", "text/markdown; charset=utf-8")
    h.send_header("Content-Length", str(len(body)))
    h.send_header("Cache-Control", "no-store")
    h.send_header("X-Content-Type-Options", "nosniff")
    if query.get("download"):
        safe = re.sub(r"[^\w. -]", "_", entry["name"])
        h.send_header("Content-Disposition", f'attachment; filename="{safe}"')
    h.end_headers()
    if h.command != "HEAD":
        h.wfile.write(body)
