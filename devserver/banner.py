"""Start-up messages."""


def print_token_status(has_token: bool) -> None:
    if has_token:
        print("HF_TOKEN: loaded (bucket requests will be proxied server-side)")
    else:
        print("HF_TOKEN: NOT FOUND - the Collection page will show a setup message.")
        print("           Create a .dev.vars file with:  HF_TOKEN=hf_xxx")
        print("           Or set the env var:            $env:HF_TOKEN = 'hf_xxx'")


def print_serving(directory: str, host: str, port: int) -> None:
    print(f"Serving {directory}")
    print(f"  Site:       http://{host}:{port}/")
    print(f"  Collection: http://{host}:{port}/collection.html")
    print("Press Ctrl+C to stop.")
