"""Build root/data/anime-watch.json from AnimeWatchURL.json.

AnimeWatchURL.json is the source of truth and is only ever READ here.
The site (js/collection.js) loads the generated {"Title": "url"} map and uses it
for the "Watch" buttons; titles not listed fall back to a Crunchyroll search.

    python tools/make_watch_links.py
    python tools/make_watch_links.py --source other.json --out some/path.json
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", default=ROOT / "AnimeWatchURL.json", type=Path)
    ap.add_argument("--out", default=ROOT / "root" / "data" / "anime-watch.json", type=Path)
    ap.add_argument("--platform", default="crunchyroll")
    args = ap.parse_args()

    data = json.loads(args.source.read_text(encoding="utf-8"))
    links = {}
    for item in data.get("anime", []):
        title = str(item.get("title", "")).strip()
        p = (item.get("platforms") or {}).get(args.platform) or {}
        url = str(p.get("url", "")).strip()
        if title and url.startswith("https://") and p.get("available", True):
            links[title] = url
        else:
            print(f"skipped: {title or item.get('id')}", file=sys.stderr)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(links, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(links)} links -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
