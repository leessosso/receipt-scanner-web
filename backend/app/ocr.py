"""Optional OCR stage that runs on the perspective-corrected receipt image.

Kept separate from :mod:`app.image_processing` so the detection/warp core has no
hard dependency on Tesseract. ``extract_receipt`` takes the flattened BGR image
produced by ``transform_receipt`` and returns raw text plus best-effort
structured fields.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import cv2
import numpy as np
import pytesseract


@dataclass
class LineItem:
    description: str
    amount: float


@dataclass
class ReceiptData:
    raw_text: str
    merchant: str | None = None
    date: str | None = None
    subtotal: float | None = None
    tax: float | None = None
    total: float | None = None
    items: list[LineItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "raw_text": self.raw_text,
            "merchant": self.merchant,
            "date": self.date,
            "subtotal": self.subtotal,
            "tax": self.tax,
            "total": self.total,
            "items": [
                {"description": item.description, "amount": item.amount}
                for item in self.items
            ],
        }


_AMOUNT_RE = re.compile(r"(-?\$?\s?\d{1,3}(?:[,.]\d{3})*[.,]\d{2})")
_TRAILING_AMOUNT_RE = re.compile(r"(-?\$?\s?\d{1,3}(?:[,.]\d{3})*[.,]\d{2})\s*$")
_KEYWORD_RE = re.compile(
    r"\b(total|subtotal|sub-total|tax|vat|gst|balance|change|cash|card|"
    r"amount|due|tip|tender)\b",
    re.IGNORECASE,
)
_DATE_PATTERNS = [
    re.compile(r"\b(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})\b"),
    re.compile(r"\b(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})\b"),
    re.compile(
        r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"[a-z]*\.?\s+\d{2,4})\b",
        re.IGNORECASE,
    ),
]


def _to_number(raw: str) -> float | None:
    cleaned = re.sub(r"[^\d.,-]", "", raw)
    cleaned = re.sub(r",(?=\d{3}\b)", "", cleaned)
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _amount_on_line(line: str) -> float | None:
    match = _TRAILING_AMOUNT_RE.search(line) or _AMOUNT_RE.search(line)
    return _to_number(match.group(1)) if match else None


def _find_date(lines: list[str]) -> str | None:
    for line in lines:
        for pattern in _DATE_PATTERNS:
            match = pattern.search(line)
            if match:
                return match.group(1)
    return None


def parse_receipt(raw_text: str) -> ReceiptData:
    """Extract structured fields from noisy OCR text using forgiving heuristics."""
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    data = ReceiptData(raw_text=raw_text)

    for line in lines:
        if re.search(r"[A-Za-z]", line):
            data.merchant = line
            break

    data.date = _find_date(lines)

    for line in lines:
        lower = line.lower()
        amount = _amount_on_line(line)
        if amount is None:
            continue

        if re.search(r"\bsub[-\s]?total\b", lower):
            data.subtotal = amount
        elif re.search(r"\b(tax|vat|gst)\b", lower):
            data.tax = amount
        elif re.search(r"\b(total|balance|amount due|due)\b", lower):
            data.total = amount if data.total is None else max(data.total, amount)
        elif not _KEYWORD_RE.search(lower):
            description = _TRAILING_AMOUNT_RE.sub("", line).strip()
            if len(description) > 1:
                data.items.append(LineItem(description=description, amount=amount))

    return data


def _preprocess_for_ocr(image: np.ndarray) -> np.ndarray:
    """Binarize the image to improve OCR accuracy on receipt text."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
    )


def extract_receipt(image: np.ndarray, lang: str = "eng") -> ReceiptData:
    """Run Tesseract on a (already perspective-corrected) receipt image."""
    processed = _preprocess_for_ocr(image)
    raw_text = pytesseract.image_to_string(processed, lang=lang)
    return parse_receipt(raw_text)
