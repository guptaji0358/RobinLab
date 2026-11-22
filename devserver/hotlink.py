"""Mirror of the Pages Function: refuse other sites and direct page loads."""

import urllib.parse


def is_hotlink(h) -> bool:
    site = h.headers.get("Sec-Fetch-Site")
    dest = h.headers.get("Sec-Fetch-Dest")
    if site:
        return site == "cross-site" or dest in ("document", "iframe", "embed", "object")
    referer = h.headers.get("Referer")
    if not referer:
        return False
    return urllib.parse.urlsplit(referer).netloc != h.headers.get("Host", "")
