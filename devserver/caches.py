"""In-memory caches. The dicts are mutated in place, never rebound."""

lqip_cache: dict[str, object] = {"key": "", "map": {}}
listing_cache: dict[str, object] = {"at": 0.0, "files": None, "thumbs": None}
skills_cache: dict[str, object] = {"at": 0.0, "items": None}
