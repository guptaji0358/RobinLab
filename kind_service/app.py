"""Kind service — FastAPI app for a Hugging Face Space.

    GET  /kinds      -> {"<bucket path>": {"w": 3840, "h": 2160}, ...}   (header X-Kind-Key)
    POST /refresh    -> scan the bucket now; only NEW or CHANGED images are examined
    GET  /health     -> {"ok": true, "count": N, "scanning": false}

Why: the lightbox's Kind/Quality (e.g. "4K UHD · Landscape") needs the pixel size. Instead
of every visitor downloading the full image to find out, this service reads just the first
~128 KB of each image (the header) ONCE, stores the result, and serves it to everyone.
An image is re-examined only if its size or upload date in the bucket changes.

READ-ONLY on the vault bucket. Results are saved in MongoDB (collection `kinds`, one
document per image, _id = bucket path), so they survive restarts and are shared by all.

Environment (Space -> Settings -> Variables and secrets)
    HF_TOKEN         READ access to the bucket
    MONGODB_URI      e.g. mongodb+srv://user:pass@cluster.mongodb.net  (Atlas free tier works)
    MONGODB_DB       optional, defaults to robinlab
    KIND_KEY         shared secret sent in X-Kind-Key
    BUCKET_ID        optional, defaults to robinlabdev/robinvault
"""

from __future__ import annotations

import hmac
import io
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

import httpx
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

BUCKET_ID = os.environ.get("BUCKET_ID", "robinlabdev/robinvault")
HF = "https://huggingface.co"
EXT = (".png", ".jpg", ".jpeg", ".webp")
RESERVED_PREFIX = "_thumbs/"
HEAD_BYTES = 131072

app = FastAPI(title="RobinLab kind service", docs_url=None, redoc_url=None, openapi_url=None)
_lock = threading.Lock()
_state: dict = {"data": {}, "scanning": False}  # data: path -> {w,h,k}


def _check(provided: str | None) -> None:
    expected = os.environ.get("KIND_KEY", "")
    if not expected:
        raise HTTPException(500, "KIND_KEY is not configured.")
    if not provided or not hmac.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(403, "Forbidden.")


_coll = None


def _kinds():
    """The MongoDB collection, or None when MONGODB_URI is not set (memory only)."""
    global _coll
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        return None
    if _coll is None:
        from pymongo import MongoClient

        _coll = MongoClient(uri, serverSelectionTimeoutMS=8000)[os.environ.get("MONGODB_DB", "robinlab")]["kinds"]
    return _coll


def _load() -> None:
    try:
        coll = _kinds()
        if coll is not None:
            _state["data"] = {d["_id"]: {"w": d["w"], "h": d["h"], "k": d["k"]} for d in coll.find()}
    except Exception:  # unreachable DB: start empty, scan will refill
        _state["data"] = {}


def _save(upserts: dict, removed: list) -> None:
    from pymongo import ReplaceOne

    coll = _kinds()
    if coll is None:
        return
    ops = [ReplaceOne({"_id": p}, {"_id": p, **v}, upsert=True) for p, v in upserts.items()]
    if ops:
        coll.bulk_write(ops, ordered=False)
    if removed:
        coll.delete_many({"_id": {"$in": removed}})


def _head(client: httpx.Client, path: str) -> bytes:
    """First HEAD_BYTES of one object. Streams and stops early, even if Range is ignored."""
    url = f"{HF}/buckets/{BUCKET_ID}/resolve/{quote(path, safe='')}"
    auth = {"Authorization": f"Bearer {os.environ['HF_TOKEN']}"}
    for _ in range(4):
        with client.stream("GET", url, headers={**auth, "Range": f"bytes=0-{HEAD_BYTES - 1}"}) as res:
            if 300 <= res.status_code < 400 and res.headers.get("location"):
                url, auth = res.headers["location"], {}  # signed CDN URL: no token
                continue
            if res.status_code not in (200, 206):
                raise RuntimeError(f"HTTP {res.status_code}")
            buf = bytearray()
            for chunk in res.iter_bytes(16384):
                buf += chunk
                if len(buf) >= HEAD_BYTES:
                    break
            return bytes(buf[:HEAD_BYTES])
    raise RuntimeError("too many redirects")


def _size(data: bytes) -> tuple[int, int]:
    from PIL import Image

    with Image.open(io.BytesIO(data)) as img:  # header only; a truncated file is fine
        w, h = img.size
        # Only JPEG carries rotation in its header; PNG/WebP getexif() would need the whole file.
        if img.format == "JPEG" and img.getexif().get(0x0112, 1) in (5, 6, 7, 8):
            w, h = h, w
    return w, h


def scan() -> None:
    with _lock:
        if _state["scanning"]:
            return
        _state["scanning"] = True
    try:
        tree = httpx.get(
            f"{HF}/api/buckets/{BUCKET_ID}/tree?recursive=true",
            headers={"Authorization": f"Bearer {os.environ['HF_TOKEN']}"}, timeout=60,
        ).json()
        live = {
            e["path"]: f"{e.get('size')}|{e.get('uploadedAt') or ''}"
            for e in tree
            if e.get("type") == "file" and e["path"].lower().endswith(EXT) and not e["path"].startswith(RESERVED_PREFIX)
        }
        data = _state["data"]
        todo = [p for p, k in live.items() if data.get(p, {}).get("k") != k]
        found: dict = {}
        if todo:
            def one(path: str):
                with httpx.Client(timeout=60, follow_redirects=False) as client:
                    return path, _size(_head(client, path))

            with ThreadPoolExecutor(max_workers=12) as pool:
                for fut in [pool.submit(one, p) for p in todo]:
                    try:
                        path, (w, h) = fut.result()
                        found[path] = {"w": w, "h": h, "k": live[path]}
                    except Exception:
                        pass  # try again on the next refresh
        data.update(found)
        gone = [p for p in data if p not in live]
        for p in gone:
            del data[p]
        if found or gone:
            _save(found, gone)
    finally:
        _state["scanning"] = False


@app.on_event("startup")
def startup() -> None:
    _load()
    threading.Thread(target=scan, daemon=True).start()


@app.get("/health")
def health() -> dict:
    return {"ok": True, "count": len(_state["data"]), "scanning": _state["scanning"]}


@app.get("/kinds")
def kinds(x_kind_key: str | None = Header(default=None)) -> JSONResponse:
    _check(x_kind_key)
    out = {p: {"w": v["w"], "h": v["h"]} for p, v in _state["data"].items()}
    return JSONResponse(out, headers={"Cache-Control": "public, max-age=60"})


@app.post("/refresh")
def refresh(tasks: BackgroundTasks, x_kind_key: str | None = Header(default=None)) -> dict:
    _check(x_kind_key)
    tasks.add_task(scan)
    return {"started": not _state["scanning"]}


@app.exception_handler(HTTPException)
def http_error(_, exc: HTTPException) -> JSONResponse:
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)
