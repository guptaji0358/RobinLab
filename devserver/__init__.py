"""Local preview server for the RobinLab site (split out of the old single-file dev_server.py).

`dev_server.py` at the repo root is the launcher. Modules are grouped by concern:

    core/        config, paths, settings, caches, b64, timefmt, content_types
    web/         HTTP handler, api_router, responses, clean_urls, hotlink
    hf/          Hugging Face bucket access: http, stream, listing, lqip
    collection/  /api/collection/{file,files,backdrop} and /decks routes
    share/       signed share links: route, create, resolve, tokens
    download/    watermarked download: route, local, relay
    skills/      Claude skills: routes, store, ids, frontmatter, summary
    canva/       Edit in Canva OAuth + edit flow
    app/         server main, cli, banner

Dependencies point one way: app -> web -> (collection, share, download, skills, canva)
-> hf -> core. Imports are absolute (`from devserver.hf.listing import get_listing`).
"""
