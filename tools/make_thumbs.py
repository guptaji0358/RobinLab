#!/usr/bin/env python3
"""Generate WebP thumbnails for the RobinLab vault and store them in the bucket.

The Collection page renders a grid of every image in the private Hugging Face
bucket. Those files are full resolution (often over 1 MB each), so using them as
grid thumbnails would mean pulling hundreds of megabytes just to browse.

This script makes a small WebP copy of each image and uploads it back into the
same bucket under a reserved `_thumbs/` prefix:

    wallpapers/foo.png   ->   _thumbs/wallpapers/foo.png.webp

Storage stays in Hugging Face — nothing is kept on the web host. The proxy
automatically falls back to the full-resolution file when a thumbnail is
missing, so the site keeps working if you add images and forget to re-run this.

Usage:
    python tools/make_thumbs.py                 # add any missing thumbnails
    python tools/make_thumbs.py --dry-run       # show what would happen
    python tools/make_thumbs.py --force         # rebuild every thumbnail
    python tools/make_thumbs.py --width 900     # max edge in px (default 720)
    python tools/make_thumbs.py --quality 85    # WebP quality (default 78)
    python tools/make_thumbs.py --prune         # also drop orphaned thumbnails

Original files are never modified or deleted. `--prune` only ever removes files
inside the `_thumbs/` prefix.
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BUCKET_ID = "robinlabdev/robinvault"
HF = "https://huggingface.co"

# Reserved prefix for generated thumbnails. The proxy hides this from the grid.
THUMB_PREFIX = "_thumbs/"

DEFAULT_WIDTH = 720
DEFAULT_QUALITY = 78
LQIP_PATH = THUMB_PREFIX + "_lqip.json"
LQIP_EDGE = 24  # px - the blurred placeholder is a ~200 byte WebP
DEFAULT_JOBS = 6
UPLOAD_BATCH = 8


# --------------------------------------------------------------------------- #
# Token
# --------------------------------------------------------------------------- #
def load_token(project_root: str) -> str | None:
    token = os.environ.get("HF_TOKEN")
    if token and token.strip():
        return token.strip()

    dev_vars = os.path.join(project_root, ".dev.vars")
    if os.path.isfile(dev_vars):
        with open(dev_vars, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                if key.strip() == "HF_TOKEN":
                    candidate = value.strip().strip("'\"")
                    if candidate:
                        return candidate

    try:
        from huggingface_hub import get_token

        stored = get_token()
        if stored:
            return stored
    except Exception:  # noqa: BLE001 - optional fallback
        pass
    return None


# --------------------------------------------------------------------------- #
# Bucket I/O
# --------------------------------------------------------------------------- #
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Stop urllib from following the 302 itself.

    The redirect target is a signed CDN URL that must NOT receive the Hugging
    Face token, so the hop is performed manually instead.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def list_tree(token: str) -> list[dict]:
    req = urllib.request.Request(f"{HF}/api/buckets/{BUCKET_ID}/tree?recursive=true")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_bytes(token: str, path: str) -> bytes:
    encoded = urllib.parse.quote(path, safe="")
    req = urllib.request.Request(f"{HF}/buckets/{BUCKET_ID}/resolve/{encoded}")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with _opener.open(req, timeout=300) as resp:
            return resp.read()
    except urllib.error.HTTPError as err:
        if err.code in (301, 302, 303, 307, 308):
            location = err.headers.get("Location")
            err.close()
            if not location:
                raise RuntimeError(f"no redirect target for {path}") from None
            # Token deliberately omitted: the CDN URL is already signed.
            with urllib.request.urlopen(location, timeout=300) as resp:
                return resp.read()
        raise


def thumb_remote_path(original_path: str) -> str:
    # Keep the original extension in the name so `a.png` and `a.jpg` can never
    # collide on the same thumbnail.
    return f"{THUMB_PREFIX}{original_path}.webp"


# --------------------------------------------------------------------------- #
# Image processing
# --------------------------------------------------------------------------- #
def make_thumb(data: bytes, max_edge: int, quality: int) -> tuple[bytes, tuple[int, int]]:
    from PIL import Image, ImageOps

    with Image.open(io.BytesIO(data)) as img:
        img = ImageOps.exif_transpose(img)
        img.thumbnail((max_edge, max_edge), Image.LANCZOS)
        has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
        img = img.convert("RGBA" if has_alpha else "RGB")
        buffer = io.BytesIO()
        img.save(buffer, "WEBP", quality=quality, method=6)
        return buffer.getvalue(), img.size


def make_lqip(data: bytes) -> list:
    """[width, height, base64 WebP] - a tiny blurred stand-in that also fixes the aspect ratio."""
    from PIL import Image

    with Image.open(io.BytesIO(data)) as img:
        width, height = img.size
        img = img.convert("RGB")
        img.thumbnail((LQIP_EDGE, LQIP_EDGE), Image.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, "WEBP", quality=40, method=6)
    return [width, height, base64.b64encode(buffer.getvalue()).decode("ascii")]


def process_lqip(entry: dict, token: str) -> tuple[str, list]:
    """Placeholder for an image whose preview already exists: read the small preview, not the original."""
    return entry["path"], make_lqip(fetch_bytes(token, thumb_remote_path(entry["path"])))


def process(entry: dict, token: str, max_edge: int, quality: int) -> dict:
    """Download one image and return its encoded thumbnail."""
    path = entry["path"]
    original = fetch_bytes(token, path)
    thumb, size = make_thumb(original, max_edge, quality)
    return {
        "lqip": make_lqip(thumb),
        "path": path,
        "remote": thumb_remote_path(path),
        "data": thumb,
        "original_bytes": len(original),
        "thumb_bytes": len(thumb),
        "dimensions": size,
    }


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main() -> int:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH, help=f"max edge in px (default {DEFAULT_WIDTH})")
    parser.add_argument("--quality", type=int, default=DEFAULT_QUALITY, help=f"WebP quality (default {DEFAULT_QUALITY})")
    parser.add_argument("--jobs", type=int, default=DEFAULT_JOBS, help=f"parallel downloads (default {DEFAULT_JOBS})")
    parser.add_argument("--limit", type=int, default=0, help="only process the first N images (0 = all)")
    parser.add_argument("--force", action="store_true", help="rebuild thumbnails that already exist")
    parser.add_argument("--prune", action="store_true", help="delete thumbnails whose original is gone")
    parser.add_argument("--dry-run", action="store_true", help="list the work without uploading anything")
    args = parser.parse_args()

    try:
        import PIL  # noqa: F401
    except ImportError:
        print("error: Pillow is required.  Install it with:  pip install Pillow", file=sys.stderr)
        return 1

    token = load_token(project_root)
    if not token:
        print("error: no Hugging Face token found.", file=sys.stderr)
        print("       Run `hf auth login`, or set HF_TOKEN, or add it to .dev.vars", file=sys.stderr)
        return 1

    print(f"Bucket: {BUCKET_ID}")
    try:
        tree = list_tree(token)
    except Exception as err:  # noqa: BLE001
        print(f"error: could not list the bucket: {err}", file=sys.stderr)
        return 1

    files = [entry for entry in tree if entry.get("type") == "file"]
    existing_thumbs = {entry["path"] for entry in files if entry["path"].startswith(THUMB_PREFIX)}
    originals = [
        entry
        for entry in files
        if not entry["path"].startswith(THUMB_PREFIX)
        and str(entry.get("contentType") or "").startswith("image/")
    ]
    originals.sort(key=lambda entry: entry["path"])

    print(f"Found {len(originals)} image(s) and {len(existing_thumbs)} existing thumbnail(s).")

    pending = []
    skipped = 0
    for entry in originals:
        if not args.force and thumb_remote_path(entry["path"]) in existing_thumbs:
            skipped += 1
            continue
        pending.append(entry)

    if args.limit:
        pending = pending[: args.limit]

    print(f"To generate: {len(pending)}   already present: {skipped}")
    if args.dry_run:
        for entry in pending:
            print(f"  would create {thumb_remote_path(entry['path'])}")
        return 0
    if not pending:
        print("Nothing to do.")

    # -- generate ---------------------------------------------------------- #
    results: list[dict] = []
    failures: list[tuple[str, str]] = []
    done = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = {
            pool.submit(process, entry, token, args.width, args.quality): entry["path"] for entry in pending
        }
        for future in concurrent.futures.as_completed(futures):
            source = futures[future]
            done += 1
            try:
                results.append(future.result())
                item = results[-1]
                print(
                    f"  [{done}/{len(pending)}] {source} -> "
                    f"{item['dimensions'][0]}x{item['dimensions'][1]} "
                    f"{item['original_bytes'] // 1024} KB -> {item['thumb_bytes'] // 1024} KB"
                )
            except Exception as err:  # noqa: BLE001 - keep going, report at the end
                failures.append((source, str(err)))
                print(f"  [{done}/{len(pending)}] {source} -> FAILED: {err}")

    # -- upload ------------------------------------------------------------ #
    if results:
        from huggingface_hub import HfApi

        api = HfApi()
        print(f"\nUploading {len(results)} thumbnail(s) to {THUMB_PREFIX} ...")
        for start in range(0, len(results), UPLOAD_BATCH):
            batch = results[start : start + UPLOAD_BATCH]
            api.batch_bucket_files(
                BUCKET_ID,
                add=[(item["data"], item["remote"]) for item in batch],
                token=token,
            )
            print(f"  uploaded {min(start + UPLOAD_BATCH, len(results))}/{len(results)}")

    # -- placeholders ------------------------------------------------------ #
    lqip: dict = {}
    if LQIP_PATH in existing_thumbs:
        try:
            lqip = json.loads(fetch_bytes(token, LQIP_PATH).decode("utf-8"))
        except Exception:  # noqa: BLE001 - rebuilt below
            lqip = {}
    before = dict(lqip)
    for item in results:
        lqip[item["path"]] = item["lqip"]
    have_thumb = existing_thumbs | {item["remote"] for item in results}
    todo = [e for e in originals if e["path"] not in lqip and thumb_remote_path(e["path"]) in have_thumb]
    if todo:
        print(f"\nBuilding {len(todo)} blurred placeholder(s) from the existing previews ...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
            for future in concurrent.futures.as_completed([pool.submit(process_lqip, e, token) for e in todo]):
                try:
                    path, value = future.result()
                    lqip[path] = value
                except Exception as err:  # noqa: BLE001
                    print(f"  placeholder failed: {err}")
    live_paths = {entry["path"] for entry in originals}
    lqip = {path: value for path, value in lqip.items() if path in live_paths}
    if lqip != before:
        from huggingface_hub import HfApi

        payload = json.dumps(lqip, separators=(",", ":")).encode("utf-8")
        HfApi().batch_bucket_files(BUCKET_ID, add=[(payload, LQIP_PATH)], token=token)
        print(f"Uploaded {LQIP_PATH}: {len(lqip)} placeholder(s), {len(payload) // 1024} KB")

    # -- prune ------------------------------------------------------------- #
    if args.prune:
        live = {thumb_remote_path(entry["path"]) for entry in originals}
        orphans = sorted(existing_thumbs - live - {LQIP_PATH})
        if orphans:
            from huggingface_hub import HfApi

            print(f"\nPruning {len(orphans)} orphaned thumbnail(s) ...")
            api = HfApi()
            for start in range(0, len(orphans), UPLOAD_BATCH):
                batch = orphans[start : start + UPLOAD_BATCH]
                api.batch_bucket_files(BUCKET_ID, delete=batch, token=token)
                print(f"  deleted {min(start + UPLOAD_BATCH, len(orphans))}/{len(orphans)}")
        else:
            print("\nNo orphaned thumbnails to prune.")

    # -- summary ----------------------------------------------------------- #
    print()
    total_original = sum(item["original_bytes"] for item in results)
    total_thumb = sum(item["thumb_bytes"] for item in results)
    print(f"Generated {len(results)} thumbnail(s).")
    if results:
        print(
            f"  grid payload: {total_original / 1_048_576:.1f} MB -> {total_thumb / 1_048_576:.1f} MB "
            f"({100 * total_thumb / max(total_original, 1):.1f}% of the originals)"
        )
    if skipped:
        print(f"  skipped {skipped} already-present thumbnail(s) (use --force to rebuild)")
    if failures:
        print(f"  {len(failures)} failure(s):")
        for path, message in failures:
            print(f"    {path}: {message}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
