from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_transform_image_response(skewed_receipt_jpeg):
    response = client.post(
        "/api/receipt/transform",
        files={"file": ("receipt.jpg", skewed_receipt_jpeg, "image/jpeg")},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["x-receipt-detected"] == "true"
    assert response.content[:2] == b"\xff\xd8"  # JPEG magic bytes


def test_transform_json_with_ocr(skewed_receipt_jpeg):
    response = client.post(
        "/api/receipt/transform",
        params={"response_format": "json", "ocr": "true"},
        files={"file": ("receipt.jpg", skewed_receipt_jpeg, "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["detected"] is True
    assert body["image_base64"]
    assert body["ocr"]["merchant"] == "CORNER MARKET"
    assert body["ocr"]["total"] == 24.36


def test_transform_json_without_ocr_omits_ocr(skewed_receipt_jpeg):
    response = client.post(
        "/api/receipt/transform",
        params={"response_format": "json"},
        files={"file": ("receipt.jpg", skewed_receipt_jpeg, "image/jpeg")},
    )
    assert response.status_code == 200
    assert "ocr" not in response.json()


def test_ocr_with_image_format_is_rejected(skewed_receipt_jpeg):
    response = client.post(
        "/api/receipt/transform",
        params={"response_format": "image", "ocr": "true"},
        files={"file": ("receipt.jpg", skewed_receipt_jpeg, "image/jpeg")},
    )
    assert response.status_code == 400


def test_non_image_upload_rejected():
    response = client.post(
        "/api/receipt/transform",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 415


def test_empty_upload_rejected():
    response = client.post(
        "/api/receipt/transform",
        files={"file": ("empty.jpg", b"", "image/jpeg")},
    )
    assert response.status_code == 400
