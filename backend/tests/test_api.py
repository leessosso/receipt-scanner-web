from app.google_store import SavedReceipt
from app.main import app, get_receipt_store
from fastapi.testclient import TestClient

client = TestClient(app)


class FakeStore:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def save(self, **kwargs):
        self.calls.append(kwargs)
        return SavedReceipt(
            file_id="file123",
            file_url="https://drive.google.com/file/d/file123/view",
            spreadsheet_id="sheet123",
        )


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


def test_create_receipt_saves_to_store(skewed_receipt_jpeg):
    store = FakeStore()
    app.dependency_overrides[get_receipt_store] = lambda: store
    try:
        response = client.post(
            "/api/receipts",
            data={"date": "2026-08-18", "amount": "6,300", "memo": "점심"},
            files={"file": ("receipt.jpg", skewed_receipt_jpeg, "image/jpeg")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["file_id"] == "file123"
    assert body["file_url"].endswith("/file123/view")
    assert body["spreadsheet_id"] == "sheet123"
    assert len(store.calls) == 1
    assert store.calls[0]["date"] == "2026-08-18"
    assert store.calls[0]["amount"] == 6300.0
    assert store.calls[0]["memo"] == "점심"
    assert store.calls[0]["filename"].startswith("2026-08-18_")


def test_create_receipt_rejects_invalid_amount(skewed_receipt_jpeg):
    app.dependency_overrides[get_receipt_store] = lambda: FakeStore()
    try:
        response = client.post(
            "/api/receipts",
            data={"date": "2026-08-18", "amount": "abc", "memo": ""},
            files={"file": ("receipt.jpg", skewed_receipt_jpeg, "image/jpeg")},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


def test_create_receipt_rejects_invalid_date(skewed_receipt_jpeg):
    app.dependency_overrides[get_receipt_store] = lambda: FakeStore()
    try:
        response = client.post(
            "/api/receipts",
            data={"date": "18-08-2026", "amount": "1000", "memo": ""},
            files={"file": ("receipt.jpg", skewed_receipt_jpeg, "image/jpeg")},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


def test_create_receipt_rejects_non_image():
    app.dependency_overrides[get_receipt_store] = lambda: FakeStore()
    try:
        response = client.post(
            "/api/receipts",
            data={"date": "2026-08-18", "amount": "1000", "memo": ""},
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 415


def test_create_receipt_unconfigured_returns_503(monkeypatch, skewed_receipt_jpeg):
    def boom() -> None:
        raise RuntimeError("GOOGLE_SPREADSHEET_ID and GOOGLE_DRIVE_FOLDER_ID are required.")

    monkeypatch.setattr("app.main.GoogleReceiptStore.from_env", boom)
    response = client.post(
        "/api/receipts",
        data={"date": "2026-08-18", "amount": "1000", "memo": ""},
        files={"file": ("receipt.jpg", skewed_receipt_jpeg, "image/jpeg")},
    )
    assert response.status_code == 503


def test_create_receipt_store_failure_returns_502(skewed_receipt_jpeg):
    class FailingStore:
        def save(self, **kwargs):
            raise RuntimeError("drive down")

    app.dependency_overrides[get_receipt_store] = lambda: FailingStore()
    try:
        response = client.post(
            "/api/receipts",
            data={"date": "2026-08-18", "amount": "1000", "memo": ""},
            files={"file": ("receipt.jpg", skewed_receipt_jpeg, "image/jpeg")},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 502
