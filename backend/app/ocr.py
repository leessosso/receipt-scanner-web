"""Optional OCR stage that runs on the perspective-corrected receipt image.

Kept separate from :mod:`app.image_processing` so the detection/warp core has no
hard dependency on Tesseract. ``extract_receipt`` takes the flattened BGR image
produced by ``transform_receipt`` and returns raw text plus best-effort
structured fields.
"""

from __future__ import annotations

import re
import statistics
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
    currency: str | None = None
    items: list[LineItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "raw_text": self.raw_text,
            "merchant": self.merchant,
            "date": self.date,
            "subtotal": self.subtotal,
            "tax": self.tax,
            "total": self.total,
            "currency": self.currency,
            "items": [
                {"description": item.description, "amount": item.amount}
                for item in self.items
            ],
        }


# Matches money-like tokens in either style:
#   US/decimal: 24.36, 1,234.50
#   KRW/integer with thousands separators: 6,300  18,400  1,055,000
#   plain integers: 3500
_MONEY = r"\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+\.\d{2}|\d{3,}"
_AMOUNT_RE = re.compile(r"[₩$]?\s?(-?(?:" + _MONEY + r"))")
_TRAILING_AMOUNT_RE = re.compile(r"[₩$]?\s?(-?(?:" + _MONEY + r"))\s*원?\s*$")
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
    negative = raw.strip().startswith("-")
    cleaned = re.sub(r"[^\d.,]", "", raw)
    if not cleaned:
        return None

    # A trailing ".dd" (1-2 digits) is treated as a decimal point; commas are
    # thousands separators. Otherwise every separator is a thousands separator
    # and the value is an integer (KRW style).
    if re.search(r"\.\d{1,2}$", cleaned):
        cleaned = cleaned.replace(",", "")
    else:
        cleaned = cleaned.replace(",", "").replace(".", "")

    try:
        value = float(cleaned)
    except ValueError:
        return None
    return -value if negative else value


def _detect_currency(text: str) -> str | None:
    if "₩" in text or "원" in text:
        return "KRW"
    if "$" in text:
        return "USD"
    # No explicit symbol: infer KRW when the receipt contains Hangul.
    if re.search(r"[가-힣]", text):
        return "KRW"
    return None


def _is_merchant_candidate(line: str) -> bool:
    hangul = len(re.findall(r"[가-힣]", line))
    latin = len(re.findall(r"[A-Za-z]", line))
    return hangul >= 2 or latin >= 4


def _clean_merchant(line: str) -> str:
    """Strip OCR noise (lone symbols/letters) and re-join split Hangul syllables."""
    kept = []
    for token in line.split():
        # Drop stray vertical-bar artifacts, then trim edge punctuation.
        token = token.replace("|", "")
        token = re.sub(r"^[^가-힣A-Za-z0-9]+|[^가-힣A-Za-z0-9]+$", "", token)
        if not token:
            continue
        if len(token) == 1 and re.fullmatch(r"[A-Za-z0-9]", token):  # lone letter/digit
            continue
        kept.append(token)
    cleaned = re.sub(r"(?<=[가-힣])\s+(?=[가-힣])", "", " ".join(kept))
    return cleaned.strip()


_MONEY_TOKEN_RE = re.compile(r"^[₩$]?(-?(?:" + _MONEY + r"))원?$")


def _amount_on_line(line: str) -> float | None:
    """Return the amount at the end of a (row-reconstructed) line.

    Takes the last whitespace-delimited token so that phone/business-registration
    numbers earlier in the line are not mistaken for amounts. Rejects tokens with
    internal ``digit-hyphen-digit`` runs (phone numbers, dates).
    """
    tokens = line.split()
    if not tokens:
        return None
    last = tokens[-1]
    if last in {"원", "₩"} and len(tokens) >= 2:
        last = tokens[-2]
    if re.search(r"\d[-/:]\d", last):
        return None
    match = _MONEY_TOKEN_RE.match(last)
    return _to_number(match.group(1)) if match else None


def _find_date(lines: list[str]) -> str | None:
    for line in lines:
        for pattern in _DATE_PATTERNS:
            match = pattern.search(line)
            if match:
                return match.group(1)
    return None


_SUBTOTAL_RE = re.compile(r"sub[-\s]?total|소\s*계|과\s*세", re.IGNORECASE)
_TAX_RE = re.compile(r"\b(tax|vat|gst)\b|부\s*가\s*세|세액", re.IGNORECASE)
_TOTAL_RE = re.compile(
    r"\b(total|balance|amount due|due)\b|합\s*계|총\s*액|결\s*제|받을\s*금액|"
    r"합계금액",
    re.IGNORECASE,
)
# Korean receipts label totals/tax/etc. with these words; treat as non-item.
_KO_KEYWORD_RE = re.compile(
    r"소\s*계|합\s*계|총\s*액|부\s*가\s*세|세액|과세|면세|결\s*제|카드|현금|"
    r"받을\s*금액|거스름|봉사료|승인|잔액"
)
_HANGUL_OR_ALPHA_RE = re.compile(r"[A-Za-z가-힣]")


def parse_receipt(raw_text: str) -> ReceiptData:
    """Extract structured fields from noisy OCR text using forgiving heuristics.

    Handles both English and Korean receipts (keyword synonyms for total/tax/
    subtotal, and Hangul-aware merchant detection).
    """
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    data = ReceiptData(raw_text=raw_text, currency=_detect_currency(raw_text))

    for line in lines:
        # First line that reads like a name (enough Hangul/Latin letters),
        # skipping OCR noise such as "S| x".
        if _is_merchant_candidate(line):
            data.merchant = _clean_merchant(line) or line
            break

    data.date = _find_date(lines)

    for line in lines:
        lower = line.lower()
        amount = _amount_on_line(line)
        if amount is None:
            continue

        if _SUBTOTAL_RE.search(line):
            data.subtotal = amount
        elif _TAX_RE.search(line):
            data.tax = amount
        elif _TOTAL_RE.search(line):
            data.total = amount if data.total is None else max(data.total, amount)
        elif not _KEYWORD_RE.search(lower) and not _KO_KEYWORD_RE.search(line):
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


def _reconstruct_lines(image: np.ndarray, lang: str) -> str:
    """Rebuild visual rows from word bounding boxes.

    Tesseract often segments two-column receipts (labels left, amounts right)
    into separate blocks, which detaches each amount from its label. Clustering
    words by their vertical center and sorting each cluster left-to-right
    restores ``label ... amount`` on a single line.
    """
    data = pytesseract.image_to_data(
        image, lang=lang, output_type=pytesseract.Output.DICT
    )
    words = []
    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if not text or conf < 30:
            continue
        words.append(
            {
                "text": text,
                "left": data["left"][i],
                "center": data["top"][i] + data["height"][i] / 2.0,
                "height": data["height"][i],
            }
        )

    if not words:
        return ""

    threshold = max(statistics.median(w["height"] for w in words) * 0.6, 8.0)
    words.sort(key=lambda w: w["center"])

    rows: list[list[dict]] = []
    current: list[dict] = []
    current_center = 0.0
    for word in words:
        if current and abs(word["center"] - current_center) > threshold:
            rows.append(current)
            current = []
        current.append(word)
        current_center = sum(w["center"] for w in current) / len(current)
    if current:
        rows.append(current)

    return "\n".join(
        _merge_split_syllables([w["text"] for w in sorted(row, key=lambda w: w["left"])])
        for row in rows
    )


def _merge_split_syllables(tokens: list[str]) -> str:
    """Join runs of single Hangul-character tokens (OCR often splits titles).

    e.g. ["미", "니", "제", "주"] -> "미니제주"; multi-character tokens and Latin
    tokens are kept as separate words.
    """
    merged: list[str] = []
    buffer: list[str] = []
    for token in tokens:
        if len(token) == 1 and re.fullmatch(r"[가-힣]", token):
            buffer.append(token)
            continue
        if buffer:
            merged.append("".join(buffer))
            buffer = []
        merged.append(token)
    if buffer:
        merged.append("".join(buffer))
    return " ".join(merged)


def extract_receipt(image: np.ndarray, lang: str = "kor+eng") -> ReceiptData:
    """Run Tesseract on a (already perspective-corrected) receipt image.

    ``lang`` defaults to ``kor+eng`` so both Korean and English receipts work;
    callers can pass a specific Tesseract language code (e.g. ``eng``).
    """
    processed = _preprocess_for_ocr(image)
    raw_text = _reconstruct_lines(processed, lang)
    if not raw_text.strip():
        raw_text = pytesseract.image_to_string(processed, lang=lang)
    return parse_receipt(raw_text)
