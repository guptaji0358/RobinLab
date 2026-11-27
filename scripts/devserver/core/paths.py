"""Filesystem locations derived from the repo layout."""

import os

PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.dirname(PACKAGE_DIR)
DEFAULT_STATIC_DIR = os.path.join(SCRIPTS_DIR, "root")
WATERMARK_DIR = os.path.join(SCRIPTS_DIR, "watermark_service")
