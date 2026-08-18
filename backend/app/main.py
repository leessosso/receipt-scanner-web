"""FastAPI application exposing the receipt perspective-correction service."""

from __future__ import annotations

import base64
import os

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from .image_processing import encode_jpeg, transform_receipt
from .ocr import extract_receipt

app = FastAPI(
    title="Receipt Scanner API",
    description=(
        "Detects a receipt in a photo and corrects perspective distortion so "
        "the receipt becomes a straight rectangle. Designed so an OCR stage can "
        "be added on top of the flattened output."
    ),
    version="1.0.0",
)

# Comma-separated list of allowed origins; defaults cover local Next.js dev.
_default_origins = "http://localhost:3000,http://127.0.0.1:3000"
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


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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
    lang: str = Query("eng", description="Tesseract language code for OCR."),
) -> Response:
    """Correct the perspective of a receipt photo.

    Returns the flattened JPEG directly (``response_format=image``) or a JSON
    envelope with a Base64 image plus detection metadata
    (``response_format=json``). When ``ocr=true`` (JSON only), the envelope also
    includes extracted text and best-effort structured fields.
    """
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported content type: {file.content_type}",
        )
    if ocr and response_format != "json":
        raise HTTPException(
            status_code=400,
            detail="OCR results require response_format=json.",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file upload.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image is too large.")

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
