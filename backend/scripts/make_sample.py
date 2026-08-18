"""Generate a synthetic angled-receipt photo for local testing.

Renders a clean receipt, then perspective-warps it onto a textured background to
mimic a phone photo taken at an angle. Output: ``samples/skewed_receipt.jpg``.
"""

from __future__ import annotations

import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _kr_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    ):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return _font(size)


def render_receipt() -> np.ndarray:
    w, h = 520, 760
    margin = 44
    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)

    title = _font(32)
    body = _font(22)

    def text_width(text: str, font) -> int:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]

    def center(text: str, font, y: int) -> None:
        draw.text(((w - text_width(text, font)) // 2, y), text, fill="black", font=font)

    def left(text: str, font, y: int) -> None:
        draw.text((margin, y), text, fill="black", font=font)

    def row(label: str, amount: str, font, y: int) -> None:
        draw.text((margin, y), label, fill="black", font=font)
        draw.text((w - margin - text_width(amount, font), y), amount, fill="black", font=font)

    divider = "-" * 30
    y = 36
    center("CORNER MARKET", title, y); y += 46
    center("123 Main Street", body, y); y += 30
    center("Tel: (555) 018-2242", body, y); y += 34
    left(divider, body, y); y += 30
    left("2026-08-18   09:42", body, y); y += 40

    for label, amount in [
        ("Coffee Beans", "$12.50"),
        ("Oat Milk", "$4.25"),
        ("Croissant", "$3.75"),
        ("Sparkling Water", "$2.00"),
    ]:
        row(label, amount, body, y); y += 34

    y += 6
    left(divider, body, y); y += 32
    row("Subtotal", "$22.50", body, y); y += 34
    row("Tax", "$1.86", body, y); y += 44
    row("TOTAL", "$24.36", title, y); y += 52
    left(divider, body, y); y += 34
    center("Thank you!", body, y)

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def render_korean_receipt() -> np.ndarray:
    w, h = 560, 780
    margin = 40
    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)

    title = _kr_font(30)
    body = _kr_font(22)

    def text_width(text: str, font) -> int:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]

    def center(text: str, font, y: int) -> None:
        draw.text(((w - text_width(text, font)) // 2, y), text, fill="black", font=font)

    def left(text: str, font, y: int) -> None:
        draw.text((margin, y), text, fill="black", font=font)

    def row(label: str, amount: str, font, y: int) -> None:
        draw.text((margin, y), label, fill="black", font=font)
        draw.text((w - margin - text_width(amount, font), y), amount, fill="black", font=font)

    divider = "-" * 28
    y = 34
    center("수확농축마트", title, y); y += 46
    center("서울 양천구 목동중앙북로 27", body, y); y += 32
    left("사업자 792-30-00222", body, y); y += 30
    left("전화 02-2649-0144", body, y); y += 34
    left(divider, body, y); y += 30
    left("거래일시 26-08-12 20:33", body, y); y += 40

    left("상품명        단가  수량   금액", body, y); y += 34
    for name, price, qty, amount in [
        ("미니제주감귤", "3,500", "1", "3,500"),
        ("롯데 웹시블럭", "2,800", "1", "2,800"),
    ]:
        row(name, amount, body, y); y += 34

    y += 6
    left(divider, body, y); y += 32
    row("과세물품", "5,728", body, y); y += 32
    row("부가세", "572", body, y); y += 40
    row("합계금액", "6,300", title, y); y += 50
    row("카드결제", "6,300", body, y); y += 34
    left(divider, body, y); y += 34
    center("교환/환불시 영수증 필요", body, y)

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def warp_onto_background(receipt: np.ndarray) -> np.ndarray:
    h, w = receipt.shape[:2]
    canvas_w, canvas_h = 900, 1100

    # Speckled gray background so the receipt edges are distinguishable.
    rng = np.random.default_rng(42)
    background = rng.integers(90, 130, size=(canvas_h, canvas_w, 3), dtype=np.uint8)

    src = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype="float32")
    dst = np.array(
        [[210, 90], [760, 190], [690, 980], [140, 840]], dtype="float32"
    )

    matrix = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(receipt, matrix, (canvas_w, canvas_h))

    mask = cv2.warpPerspective(
        np.full((h, w), 255, dtype=np.uint8), matrix, (canvas_w, canvas_h)
    )
    mask3 = cv2.merge([mask, mask, mask]) > 0
    composite = np.where(mask3, warped, background)
    return composite.astype(np.uint8)


def main() -> None:
    out_dir = os.path.join(os.path.dirname(__file__), "..", "samples")
    os.makedirs(out_dir, exist_ok=True)

    receipt = render_receipt()
    cv2.imwrite(os.path.join(out_dir, "flat_receipt.png"), receipt)

    skewed = warp_onto_background(receipt)
    cv2.imwrite(
        os.path.join(out_dir, "skewed_receipt.jpg"),
        skewed,
        [int(cv2.IMWRITE_JPEG_QUALITY), 90],
    )

    kr_receipt = render_korean_receipt()
    cv2.imwrite(os.path.join(out_dir, "flat_receipt_kor.png"), kr_receipt)
    kr_skewed = warp_onto_background(kr_receipt)
    cv2.imwrite(
        os.path.join(out_dir, "skewed_receipt_kor.jpg"),
        kr_skewed,
        [int(cv2.IMWRITE_JPEG_QUALITY), 90],
    )
    print("Wrote English and Korean samples to samples/")


if __name__ == "__main__":
    main()
