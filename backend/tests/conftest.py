"""Shared pytest fixtures.

Reuses the sample generator in ``scripts/make_sample.py`` so tests exercise the
same synthetic angled-receipt image used for manual validation.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import cv2
import numpy as np
import pytest

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_MAKE_SAMPLE_PATH = _BACKEND_DIR / "scripts" / "make_sample.py"

_spec = importlib.util.spec_from_file_location("make_sample", _MAKE_SAMPLE_PATH)
assert _spec and _spec.loader
make_sample = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(make_sample)


@pytest.fixture(scope="session")
def flat_receipt() -> np.ndarray:
    return make_sample.render_receipt()


@pytest.fixture(scope="session")
def skewed_receipt(flat_receipt: np.ndarray) -> np.ndarray:
    return make_sample.warp_onto_background(flat_receipt)


@pytest.fixture(scope="session")
def skewed_receipt_jpeg(skewed_receipt: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".jpg", skewed_receipt, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    assert ok
    return buf.tobytes()


@pytest.fixture(scope="session")
def solid_image_png() -> bytes:
    """A uniform image with no detectable document boundary (fallback case)."""
    image = np.full((400, 400, 3), 200, dtype=np.uint8)
    ok, buf = cv2.imencode(".png", image)
    assert ok
    return buf.tobytes()
