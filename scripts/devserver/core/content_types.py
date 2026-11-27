"""Which bucket content types the proxy will stream."""

# Images power the Collection grid; .pptx decks are fetched by the presentations page.
PPTX_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def is_servable(content_type: str) -> bool:
    return content_type.startswith("image/") or content_type == PPTX_TYPE
