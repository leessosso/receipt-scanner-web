"""Receipt detection and perspective-correction utilities.

The pipeline is intentionally split into small, individually testable helpers so
that additional post-processing steps (e.g. an OCR stage) can be inserted later
without touching the detection/warp core.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class TransformResult:
    """Outcome of a receipt transform attempt.

    ``image`` is always a valid BGR ``np.ndarray``. When ``detected`` is False
    the caller received the (optionally enhanced) original image as a fallback.
    """

    image: np.ndarray
    detected: bool
    message: str


def order_points(pts: np.ndarray) -> np.ndarray:
    """Order 4 points as top-left, top-right, bottom-right, bottom-left."""
    pts = pts.reshape(4, 2).astype("float32")
    ordered = np.zeros((4, 2), dtype="float32")

    # Top-left has the smallest sum, bottom-right the largest.
    s = pts.sum(axis=1)
    ordered[0] = pts[np.argmin(s)]
    ordered[2] = pts[np.argmax(s)]

    # Top-right has the smallest difference (x - y), bottom-left the largest.
    diff = np.diff(pts, axis=1).ravel()
    ordered[1] = pts[np.argmin(diff)]
    ordered[3] = pts[np.argmax(diff)]

    return ordered


def find_document_contour(image: np.ndarray) -> np.ndarray | None:
    """Return the 4 corner points of the largest quadrilateral, or None.

    Runs grayscale -> Gaussian blur -> Canny -> contour approximation. Detection
    is performed on a downscaled copy for speed and robustness, then the corner
    points are scaled back to the original resolution.
    """
    height = image.shape[0]
    if height == 0:
        return None

    ratio = height / 500.0
    small = cv2.resize(image, (int(image.shape[1] / ratio), 500))

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(gray, 75, 200)
    # Close small gaps so partially broken edges still form a closed contour.
    edged = cv2.dilate(edged, np.ones((3, 3), np.uint8), iterations=1)

    contours, _ = cv2.findContours(
        edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
    )
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

    small_area = small.shape[0] * small.shape[1]
    for contour in contours:
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
        if len(approx) == 4 and cv2.contourArea(approx) > 0.1 * small_area:
            return (approx.reshape(4, 2).astype("float32")) * ratio

    # Fallback for real photos where edges are soft/curled and no clean 4-gon is
    # found: use the rotated bounding box of the largest sizable contour.
    for contour in contours:
        if cv2.contourArea(contour) > 0.2 * small_area:
            box = cv2.boxPoints(cv2.minAreaRect(contour))
            return box.astype("float32") * ratio

    return None


def four_point_transform(image: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Apply a perspective warp so the quad defined by ``pts`` fills the frame."""
    rect = order_points(pts)
    (tl, tr, br, bl) = rect

    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    max_width = max(int(width_a), int(width_b))

    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_height = max(int(height_a), int(height_b))

    max_width = max(max_width, 1)
    max_height = max(max_height, 1)

    dst = np.array(
        [
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1],
        ],
        dtype="float32",
    )

    matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, matrix, (max_width, max_height))


def enhance(image: np.ndarray) -> np.ndarray:
    """Boost contrast and sharpen slightly to improve text legibility."""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_channel = clahe.apply(l_channel)
    merged = cv2.merge((l_channel, a_channel, b_channel))
    contrasted = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)

    sharpen_kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    return cv2.filter2D(contrasted, -1, sharpen_kernel)


def decode_image(data: bytes) -> np.ndarray | None:
    """Decode raw image bytes into a BGR ndarray, or None if invalid."""
    buffer = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    return image


def transform_receipt(data: bytes) -> TransformResult:
    """Detect a receipt in ``data`` and return a flattened, enhanced image.

    Falls back to the enhanced original when no quadrilateral is detected.
    """
    image = decode_image(data)
    if image is None:
        raise ValueError("Uploaded file is not a valid image.")

    contour = find_document_contour(image)
    if contour is None:
        return TransformResult(
            image=enhance(image),
            detected=False,
            message="No receipt boundary detected; returning enhanced original.",
        )

    warped = four_point_transform(image, contour)
    enhanced = enhance(warped)
    return TransformResult(
        image=enhanced,
        detected=True,
        message="Receipt detected and flattened.",
    )


def encode_jpeg(image: np.ndarray, quality: int = 92) -> bytes:
    """Encode a BGR ndarray as JPEG bytes."""
    success, buffer = cv2.imencode(
        ".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    )
    if not success:
        raise ValueError("Failed to encode result image.")
    return buffer.tobytes()
