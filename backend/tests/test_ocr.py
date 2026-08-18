from app.image_processing import transform_receipt
from app.ocr import extract_receipt, parse_receipt

SAMPLE_TEXT = """CORNER MARKET
123 Main Street
Tel: (555) 018-2242

2026-08-18 09:42

Coffee Beans $12.50
Oat Milk $4.25
Croissant $3.75
Sparkling Water $2.00
Subtotal $22.50
Tax $1.86
TOTAL $24.36

Thank you!
"""


def test_parse_receipt_extracts_summary_fields():
    data = parse_receipt(SAMPLE_TEXT)
    assert data.merchant == "CORNER MARKET"
    assert data.date == "2026-08-18"
    assert data.subtotal == 22.50
    assert data.tax == 1.86
    assert data.total == 24.36


def test_parse_receipt_extracts_line_items():
    data = parse_receipt(SAMPLE_TEXT)
    descriptions = {item.description: item.amount for item in data.items}
    assert descriptions["Coffee Beans"] == 12.50
    assert descriptions["Oat Milk"] == 4.25
    assert descriptions["Croissant"] == 3.75
    assert descriptions["Sparkling Water"] == 2.00
    # Keyword lines (Subtotal/Tax/TOTAL) must not be treated as items.
    assert "Subtotal" not in descriptions
    assert "TOTAL" not in descriptions


def test_parse_receipt_handles_empty_text():
    data = parse_receipt("")
    assert data.merchant is None
    assert data.total is None
    assert data.items == []


def test_parse_receipt_prefers_largest_total():
    text = "Subtotal $10.00\nTOTAL $11.50\nBalance Due $11.50"
    data = parse_receipt(text)
    assert data.total == 11.50
    assert data.subtotal == 10.00


def test_extract_receipt_reads_flattened_sample(skewed_receipt_jpeg):
    """End-to-end OCR: correct perspective then read text with Tesseract."""
    result = transform_receipt(skewed_receipt_jpeg)
    data = extract_receipt(result.image)
    assert "CORNER MARKET" in data.raw_text
    assert data.total == 24.36
    assert any(item.description.startswith("Coffee") for item in data.items)
    assert data.currency == "USD"


KOREAN_TEXT = """수확농축마트
거래일시 26-08-12 20:33
미니제주감귤 3,500
롯데 웹시블럭 2,800
과세물품 5,728
부가세 572
합계금액 6,300
카드결제 6,300
"""


def test_parse_receipt_korean_integer_amounts():
    data = parse_receipt(KOREAN_TEXT)
    assert data.currency == "KRW"
    assert data.merchant == "수확농축마트"
    assert data.date == "26-08-12"
    assert data.total == 6300
    assert data.tax == 572
    assert data.subtotal == 5728


def test_parse_receipt_korean_line_items():
    data = parse_receipt(KOREAN_TEXT)
    descriptions = {item.description: item.amount for item in data.items}
    assert descriptions.get("미니제주감귤") == 3500
    assert "합계금액" not in descriptions
    assert "부가세" not in descriptions


def test_parse_receipt_ignores_phone_and_business_numbers():
    text = "전화 02-2649-0144\n사업자 792-30-00222\n합계 6,300"
    data = parse_receipt(text)
    # Phone / business-registration numbers must not become items or totals.
    assert data.items == []
    assert data.total == 6300


def test_to_number_style_handling():
    from app.ocr import _to_number

    assert _to_number("6,300") == 6300
    assert _to_number("1,055,000") == 1055000
    assert _to_number("24.36") == 24.36
    assert _to_number("1,234.50") == 1234.50
    assert _to_number("3500") == 3500
