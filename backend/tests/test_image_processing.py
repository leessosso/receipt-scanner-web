import numpy as np

from app.image_processing import (
    find_document_contour,
    four_point_transform,
    order_points,
    transform_receipt,
)


def test_order_points_orders_corners_clockwise_from_top_left():
    # Deliberately shuffled corners of a 100x200 rectangle.
    pts = np.array([[100, 200], [0, 0], [100, 0], [0, 200]], dtype="float32")
    ordered = order_points(pts)

    np.testing.assert_array_almost_equal(ordered[0], [0, 0])  # top-left
    np.testing.assert_array_almost_equal(ordered[1], [100, 0])  # top-right
    np.testing.assert_array_almost_equal(ordered[2], [100, 200])  # bottom-right
    np.testing.assert_array_almost_equal(ordered[3], [0, 200])  # bottom-left


def test_four_point_transform_output_dimensions():
    image = np.zeros((300, 300, 3), dtype=np.uint8)
    pts = np.array([[50, 50], [250, 60], [240, 250], [40, 240]], dtype="float32")
    warped = four_point_transform(image, pts)

    # Output is a rectangle roughly matching the quad's side lengths.
    assert warped.shape[0] > 150
    assert warped.shape[1] > 150
    assert warped.shape[2] == 3


def test_find_document_contour_detects_skewed_receipt(skewed_receipt):
    contour = find_document_contour(skewed_receipt)
    assert contour is not None
    assert contour.shape == (4, 2)


def test_find_document_contour_returns_none_for_solid_image():
    solid = np.full((400, 400, 3), 200, dtype=np.uint8)
    assert find_document_contour(solid) is None


def test_transform_receipt_detected_true_on_skewed(skewed_receipt_jpeg):
    result = transform_receipt(skewed_receipt_jpeg)
    assert result.detected is True
    # Flattened receipt should be clearly taller than wide (portrait).
    height, width = result.image.shape[:2]
    assert height > width


def test_transform_receipt_fallback_on_solid(solid_image_png):
    result = transform_receipt(solid_image_png)
    assert result.detected is False
    assert result.image.shape[2] == 3


def test_transform_receipt_rejects_invalid_bytes():
    import pytest

    with pytest.raises(ValueError):
        transform_receipt(b"not an image")
