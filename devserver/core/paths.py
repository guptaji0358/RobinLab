"""Filesystem locations derived from the repo layout."""

import os

PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(PACKAGE_DIR)
DEFAULT_STATIC_DIR = os.path.join(PROJECT_ROOT, "scripts", "root")
WATERMARK_DIR = os.path.join(PROJECT_ROOT, "watermark_service")
