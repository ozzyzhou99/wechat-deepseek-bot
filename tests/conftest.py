"""Use a workspace-local temporary root on locked-down Windows machines."""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

import pytest


@pytest.fixture
def tmp_path(request):
    root = Path(__file__).resolve().parents[1] / ".test-tmp"
    path = root / f"{request.node.name}-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
