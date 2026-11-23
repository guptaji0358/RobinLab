"""The concrete request handler: HTTP verbs wired to the API router and static files."""

import urllib.parse

from devserver.web.api_router import handle_api
from devserver.web.clean_urls import resolve_clean_url
from devserver.web.handler_base import BaseHandler
from devserver.web.responses import send_json


class Handler(BaseHandler):
    def do_GET(self):  # noqa: N802 - stdlib naming
        if handle_api(self, urllib.parse.urlsplit(self.path)):
            return
        resolve_clean_url(self)
        super().do_GET()

    def do_HEAD(self):  # noqa: N802 - stdlib naming
        if handle_api(self, urllib.parse.urlsplit(self.path)):
            return
        resolve_clean_url(self)
        super().do_HEAD()

    def do_POST(self):  # noqa: N802 - stdlib naming
        if handle_api(self, urllib.parse.urlsplit(self.path)):
            return
        send_json(self, {"error": "method_not_allowed"}, 405)
