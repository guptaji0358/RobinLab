"""GET /api/collection/files: JSON manifest of the bucket."""

import urllib.parse

from devserver.core.config import BUCKET_ID
from devserver.hf.listing import get_listing
from devserver.web.responses import send_json


def serve_listing(h) -> None:
    try:
        listing = get_listing(h.token or "")
    except Exception as err:  # noqa: BLE001 - surface any upstream failure as JSON
        send_json(h, {"error": "upstream_error", "message": str(err)}, 502)
        return

    files = listing["files"]
    folders = sorted({file["folder"] for file in files})

    def url_for(path: str) -> str:
        return "/api/collection/file?path=" + urllib.parse.quote(path, safe="")

    send_json(
        h,
        {
            "bucket": BUCKET_ID,
            "count": len(files),
            "totalSize": sum(file["size"] for file in files),
            "folders": folders,
            "files": [
                {
                    **{key: value for key, value in file.items() if key not in ("thumbPath", "lqip")},
                    **(
                        {"w": file["lqip"][0], "h": file["lqip"][1], "blur": "data:image/webp;base64," + file["lqip"][2],
                         **({"ow": file["lqip"][3], "oh": file["lqip"][4]} if len(file["lqip"]) > 4 else {})}
                        if file["lqip"]
                        else {}
                    ),
                    "url": url_for(file["path"]),
                }
                for file in files
            ],
        },
        200,
        cache="public, max-age=60",
    )
