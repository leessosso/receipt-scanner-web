"""FastAPI application exposing receipt capture and Google Sheet storage."""

from __future__ import annotations

import base64
import os
import re
from datetime import datetime

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from .google_store import GoogleReceiptStore, ReceiptStore
from .image_processing import encode_jpeg, transform_receipt
from .ocr import extract_receipt

load_dotenv()

app = FastAPI(
    title="Receipt Scanner API",
    description=(
        "Upload a receipt photo with date, amount, and memo; the image is stored "
        "on Google Drive and a row is appended to Google Sheets. The original "
        "perspective-correction endpoint remains available."
    ),
    version="1.1.0",
)

# Comma-separated list of allowed origins; defaults cover local Next.js dev
# (3000, and 3001 when 3000 is already taken).
_default_origins = (
    "http://localhost:3000,http://127.0.0.1:3000,"
    "http://localhost:3001,http://127.0.0.1:3001"
)
allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", _default_origins).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Custom response headers must be explicitly exposed or cross-origin
    # browser JS cannot read them (curl is unaffected).
    expose_headers=["X-Receipt-Detected", "X-Receipt-Message"],
)

MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB


def get_receipt_store() -> ReceiptStore:
    try:
        return GoogleReceiptStore.from_env()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def parse_amount(raw: str) -> float:
    cleaned = (
        raw.strip()
        .replace(",", "")
        .replace("₩", "")
        .replace("원", "")
        .replace(" ", "")
    )
    if not cleaned:
        raise ValueError("Amount is required.")
    try:
        return float(cleaned)
    except ValueError as exc:
        raise ValueError(f"Invalid amount: {raw}") from exc


def parse_date(raw: str) -> str:
    try:
        return datetime.strptime(raw.strip(), "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise ValueError("Date must be YYYY-MM-DD.") from exc


def _read_image_upload(file: UploadFile, data: bytes) -> None:
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported content type: {file.content_type}",
        )
    if not data:
        raise HTTPException(status_code=400, detail="Empty file upload.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image is too large.")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/receipts")
async def create_receipt(
    file: UploadFile = File(...),
    date: str = Form(...),
    amount: str = Form(...),
    memo: str = Form(""),
    store: ReceiptStore = Depends(get_receipt_store),
) -> dict[str, str]:
    """Save the photo to Drive and append date/amount/memo to the configured Sheet."""
    data = await file.read()
    _read_image_upload(file, data)

    try:
        parsed_date = parse_date(date)
        parsed_amount = parse_amount(amount)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    suffix = os.path.splitext(file.filename or "")[1] or ".jpg"
    safe_name = re.sub(r"[^\w.\-]+", "_", file.filename or f"receipt{suffix}")
    filename = f"{parsed_date}_{safe_name}"

    try:
        saved = store.save(
            filename=filename,
            content=data,
            mime_type=file.content_type or "image/jpeg",
            date=parsed_date,
            amount=parsed_amount,
            memo=memo.strip(),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Failed to save the receipt to Google Drive or Sheets.",
        ) from exc

    return saved.to_dict()


@app.post("/api/receipt/transform")
async def transform(
    file: UploadFile = File(...),
    response_format: str = Query(
        "image",
        pattern="^(image|json)$",
        description="`image` returns JPEG bytes, `json` returns Base64 payload.",
    ),
    ocr: bool = Query(
        False,
        description="Run OCR on the corrected image (requires response_format=json).",
    ),
    lang: str = Query(
        "kor+eng",
        description="Tesseract language code(s) for OCR, e.g. `eng` or `kor+eng`.",
    ),
) -> Response:
    """Correct the perspective of a receipt photo.

    Returns the flattened JPEG directly (``response_format=image``) or a JSON
    envelope with a Base64 image plus detection metadata
    (``response_format=json``). When ``ocr=true`` (JSON only), the envelope also
    includes extracted text and best-effort structured fields.
    """
    if ocr and response_format != "json":
        raise HTTPException(
            status_code=400,
            detail="OCR results require response_format=json.",
        )

    data = await file.read()
    _read_image_upload(file, data)

    try:
        result = transform_receipt(data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    jpeg_bytes = encode_jpeg(result.image)

    if response_format == "json":
        payload = {
            "detected": result.detected,
            "message": result.message,
            "content_type": "image/jpeg",
            "image_base64": base64.b64encode(jpeg_bytes).decode("ascii"),
        }
        if ocr:
            payload["ocr"] = extract_receipt(result.image, lang=lang).to_dict()
        return JSONResponse(payload)

    return Response(
        content=jpeg_bytes,
        media_type="image/jpeg",
        headers={
            "X-Receipt-Detected": "true" if result.detected else "false",
            "X-Receipt-Message": result.message,
        },
    )
