from __future__ import annotations

import unicodedata
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

PAGE_WIDTH = 595.0
PAGE_HEIGHT = 842.0
MARGIN = 40.0
CONTENT_WIDTH = PAGE_WIDTH - (2 * MARGIN)
INDIA_TZ = timezone(timedelta(hours=5, minutes=30))

_TEXT_REPLACEMENTS = str.maketrans({
    "’": "'", "‘": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "…": "...", "•": "-",
    "₹": "INR ", "×": "x", "·": "-", "\u00a0": " ",
})


def clean_pdf_text(value: Any) -> str:
    text = str(value or "").translate(_TEXT_REPLACEMENTS)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    return "".join(ch if 32 <= ord(ch) <= 126 else " " for ch in text).strip()


def pdf_escape(value: Any) -> str:
    return clean_pdf_text(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def money(value: Any) -> str:
    try:
        amount = Decimal(str(value or 0)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        amount = Decimal("0.00")
    return f"INR {amount:,.2f}"


def readable_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "-"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(INDIA_TZ).strftime("%d %b %Y, %I:%M %p IST")
    except ValueError:
        return clean_pdf_text(text)


def wrap_text(value: Any, width: float, font_size: float) -> list[str]:
    text = clean_pdf_text(value) or "-"
    max_chars = max(6, int(width / max(font_size * 0.53, 1)))
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if len(word) > max_chars:
            if current:
                lines.append(current)
                current = ""
            while len(word) > max_chars:
                lines.append(word[:max_chars])
                word = word[max_chars:]
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or ["-"]


class PdfDocument:
    def __init__(self) -> None:
        self.pages: list[list[str]] = []

    def new_page(self) -> list[str]:
        page: list[str] = []
        self.pages.append(page)
        return page

    @staticmethod
    def _color(rgb: tuple[float, float, float]) -> str:
        return " ".join(f"{channel:.3f}" for channel in rgb)

    def text(self, page: list[str], x: float, y: float, value: Any, *, size: float = 10, bold: bool = False, color: tuple[float, float, float] = (0.12, 0.12, 0.12)) -> None:
        font = "F2" if bold else "F1"
        page.append(f"BT /{font} {size:.1f} Tf {self._color(color)} rg {x:.1f} {y:.1f} Td ({pdf_escape(value)}) Tj ET")

    def line(self, page: list[str], x1: float, y1: float, x2: float, y2: float, *, color: tuple[float, float, float] = (0.82, 0.82, 0.82), width: float = 0.7) -> None:
        page.append(f"{self._color(color)} RG {width:.1f} w {x1:.1f} {y1:.1f} m {x2:.1f} {y2:.1f} l S")

    def rect(self, page: list[str], x: float, y: float, width: float, height: float, *, fill: tuple[float, float, float] | None = None, stroke: tuple[float, float, float] | None = None, line_width: float = 0.7) -> None:
        commands: list[str] = []
        if fill is not None:
            commands.append(f"{self._color(fill)} rg")
        if stroke is not None:
            commands.append(f"{self._color(stroke)} RG {line_width:.1f} w")
        paint = "B" if fill is not None and stroke is not None else "f" if fill is not None else "S"
        commands.append(f"{x:.1f} {y:.1f} {width:.1f} {height:.1f} re {paint}")
        page.append(" ".join(commands))

    def build(self) -> bytes:
        total_pages = len(self.pages)
        for page_index, page in enumerate(self.pages, 1):
            self.text(page, MARGIN, 20, f"vibe4you.in  |  Page {page_index} of {total_pages}", size=7.5, color=(0.45, 0.45, 0.45))
        normal_font = 3 + (2 * total_pages)
        bold_font = normal_font + 1
        kids = " ".join(f"{3 + (2 * index)} 0 R" for index in range(total_pages))
        objects: list[bytes] = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            f"<< /Type /Pages /Kids [{kids}] /Count {total_pages} >>".encode(),
        ]
        for index, commands in enumerate(self.pages):
            page_number = 3 + (2 * index)
            content_number = page_number + 1
            stream = "\n".join(commands).encode("ascii")
            resources = f"<< /Font << /F1 {normal_font} 0 R /F2 {bold_font} 0 R >> >>"
            objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH:.0f} {PAGE_HEIGHT:.0f}] /Resources {resources} /Contents {content_number} 0 R >>".encode())
            objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
        pdf = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for number, obj in enumerate(objects, 1):
            offsets.append(len(pdf))
            pdf.extend(f"{number} 0 obj\n".encode())
            pdf.extend(obj)
            pdf.extend(b"\nendobj\n")
        xref = len(pdf)
        pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
        for offset in offsets[1:]:
            pdf.extend(f"{offset:010d} 00000 n \n".encode())
        pdf.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
        return bytes(pdf)


def _draw_brand_header(doc: PdfDocument, page: list[str], order: dict[str, Any]) -> float:
    doc.rect(page, 0, PAGE_HEIGHT - 92, PAGE_WIDTH, 92, fill=(0.06, 0.06, 0.07))
    doc.rect(page, 0, PAGE_HEIGHT - 96, PAGE_WIDTH, 4, fill=(0.52, 0.80, 0.09))
    doc.text(page, MARGIN, PAGE_HEIGHT - 48, "Vibe4You", size=23, bold=True, color=(1, 1, 1))
    doc.text(page, MARGIN, PAGE_HEIGHT - 66, "Your City. Your Shops. Your Style.", size=8.5, color=(0.80, 0.80, 0.80))
    doc.text(page, 390, PAGE_HEIGHT - 45, "RECEIPT / INVOICE", size=12, bold=True, color=(1, 1, 1))
    doc.text(page, 390, PAGE_HEIGHT - 63, f"Receipt Ref: V4Y-RCP-{order.get('id', '-')}", size=7.5, color=(0.80, 0.80, 0.80))
    return PAGE_HEIGHT - 122


def _draw_wrapped(doc: PdfDocument, page: list[str], x: float, y: float, value: Any, width: float, *, size: float = 9, bold: bool = False, color: tuple[float, float, float] = (0.18, 0.18, 0.18), line_height: float = 11) -> float:
    lines = wrap_text(value, width, size)
    for line in lines:
        doc.text(page, x, y, line, size=size, bold=bold, color=color)
        y -= line_height
    return y


def _draw_order_meta(doc: PdfDocument, page: list[str], order: dict[str, Any], y: float) -> float:
    doc.text(page, MARGIN, y, "Order reference", size=7.5, bold=True, color=(0.45, 0.45, 0.45))
    doc.text(page, MARGIN, y - 15, order.get("id", "-"), size=10.5, bold=True)
    doc.text(page, 245, y, "Order placed", size=7.5, bold=True, color=(0.45, 0.45, 0.45))
    doc.text(page, 245, y - 15, readable_date(order.get("createdAt")), size=9.2)
    doc.text(page, 405, y, "Delivered", size=7.5, bold=True, color=(0.45, 0.45, 0.45))
    delivered_at = order.get("deliveredAt") or order.get("updatedAt")
    doc.text(page, 405, y - 15, readable_date(delivered_at), size=9.2)
    doc.line(page, MARGIN, y - 30, PAGE_WIDTH - MARGIN, y - 30)
    return y - 54


def _draw_party_blocks(doc: PdfDocument, page: list[str], order: dict[str, Any], y: float) -> float:
    address = order.get("address") or {}
    gap = 14
    box_width = (CONTENT_WIDTH - gap) / 2
    box_height = 96
    doc.rect(page, MARGIN, y - box_height, box_width, box_height, fill=(0.975, 0.975, 0.975), stroke=(0.87, 0.87, 0.87))
    doc.rect(page, MARGIN + box_width + gap, y - box_height, box_width, box_height, fill=(0.975, 0.975, 0.975), stroke=(0.87, 0.87, 0.87))
    left_x = MARGIN + 12
    right_x = MARGIN + box_width + gap + 12
    top_y = y - 18
    doc.text(page, left_x, top_y, "CUSTOMER", size=7.5, bold=True, color=(0.38, 0.38, 0.38))
    doc.text(page, left_x, top_y - 17, address.get("name", "-"), size=10.5, bold=True)
    doc.text(page, left_x, top_y - 34, address.get("phone", "-"), size=9)

    doc.text(page, right_x, top_y, "DELIVERY ADDRESS", size=7.5, bold=True, color=(0.38, 0.38, 0.38))
    delivery_lines = [
        address.get("street", "-"),
        f"{address.get('city', '-')} {address.get('state', '')}".strip(),
        f"PIN {address.get('pincode', '-')}",
    ]
    delivery_y = top_y - 17
    for line in delivery_lines:
        delivery_y = _draw_wrapped(doc, page, right_x, delivery_y, line, box_width - 24, size=8.6, line_height=11)
    return y - box_height - 24


ITEM_COLUMNS = [
    ("Store", 82.0),
    ("Product", 128.0),
    ("Size", 42.0),
    ("Color", 55.0),
    ("Qty", 30.0),
    ("Unit", 72.0),
    ("Line total", 80.0),
]


def _draw_item_header(doc: PdfDocument, page: list[str], y: float) -> float:
    height = 24.0
    doc.rect(page, MARGIN, y - height, CONTENT_WIDTH, height, fill=(0.10, 0.10, 0.11))
    x = MARGIN + 5
    for title, width in ITEM_COLUMNS:
        doc.text(page, x, y - 16, title.upper(), size=6.8, bold=True, color=(1, 1, 1))
        x += width
    return y - height


def _item_cells(item: dict[str, Any]) -> list[str]:
    return [
        clean_pdf_text(item.get("storeName") or "Vibe4You"),
        clean_pdf_text(item.get("productName") or "-"),
        clean_pdf_text(item.get("size") or "-"),
        clean_pdf_text(item.get("colourName") or "-"),
        clean_pdf_text(item.get("quantity") or 0),
        money(item.get("unitPrice", 0)),
        money(item.get("lineTotal", 0)),
    ]


def _draw_item_row(doc: PdfDocument, page: list[str], item: dict[str, Any], y: float) -> float:
    cells = _item_cells(item)
    wrapped = [wrap_text(value, width - 9, 7.2) for value, (_, width) in zip(cells, ITEM_COLUMNS)]
    row_lines = max(len(lines) for lines in wrapped)
    row_height = max(30.0, 10.0 + (row_lines * 9.0))
    doc.rect(page, MARGIN, y - row_height, CONTENT_WIDTH, row_height, stroke=(0.88, 0.88, 0.88))
    x = MARGIN + 5
    for lines, (_, width) in zip(wrapped, ITEM_COLUMNS):
        text_y = y - 15
        for line in lines[:4]:
            doc.text(page, x, text_y, line, size=7.2)
            text_y -= 9
        x += width
    return y - row_height


def _new_items_page(doc: PdfDocument, order: dict[str, Any], *, continuation: bool = False) -> tuple[list[str], float]:
    page = doc.new_page()
    y = _draw_brand_header(doc, page, order)
    if continuation:
        doc.text(page, MARGIN, y, "ITEMS - CONTINUED", size=10, bold=True, color=(0.35, 0.35, 0.35))
        y -= 20
    return page, _draw_item_header(doc, page, y)


def _payment_labels(order: dict[str, Any]) -> tuple[str, str, str | None]:
    status = str(order.get("paymentStatus") or "pending").casefold()
    status_label = {"paid": "Paid", "pending": "Pending", "failed": "Failed", "refunded": "Refunded"}.get(status, clean_pdf_text(status).title())
    method = str(order.get("paymentMethod") or "-").casefold()
    collected_at: str | None = None
    if method == "cod":
        collection = str(order.get("paymentCollectionMethod") or "").casefold()
        method_label = {
            "cash": "Cash",
            "upi_at_delivery": "UPI at Delivery",
        }.get(collection, "Pay on Delivery")
        if order.get("paymentCollectedAt"):
            collected_at = readable_date(order.get("paymentCollectedAt"))
    elif method == "upi":
        method_label = "UPI via Razorpay"
    elif method == "card":
        method_label = "Card via Razorpay"
    else:
        method_label = clean_pdf_text(method).upper() or "-"
    return status_label, method_label, collected_at


def _draw_totals_and_payment(doc: PdfDocument, page: list[str], order: dict[str, Any], y: float) -> float:
    if y < 250:
        page = doc.new_page()
        y = _draw_brand_header(doc, page, order)
    box_width = 236.0
    right_x = PAGE_WIDTH - MARGIN - box_width
    totals = [
        ("Subtotal", money(order.get("subtotal", 0))),
        ("Discount", f"- {money(order.get('discount', 0))}" if Decimal(str(order.get("discount") or 0)) > 0 else money(0)),
        ("Delivery", money(order.get("deliveryFee", 0))),
        ("Tax", money(order.get("taxes", 0))),
    ]
    doc.text(page, right_x, y, "ORDER TOTAL", size=8, bold=True, color=(0.38, 0.38, 0.38))
    y -= 18
    for label, value in totals:
        doc.text(page, right_x, y, label, size=8.5)
        doc.text(page, right_x + 132, y, value, size=8.5, bold=True)
        y -= 16
    doc.line(page, right_x, y + 5, PAGE_WIDTH - MARGIN, y + 5, color=(0.40, 0.40, 0.40))
    grand_total = f"Grand Total: {money(order.get('grandTotal', 0))}"
    doc.text(page, right_x, y - 13, grand_total, size=11.5, bold=True)
    y -= 52
    status_label, method_label, collected_at = _payment_labels(order)
    payment_height = 92.0 if collected_at or order.get("paymentVerifiedAt") else 76.0
    if y - payment_height < 42:
        page = doc.new_page()
        y = _draw_brand_header(doc, page, order)
    fill = (0.94, 0.98, 0.91) if status_label == "Paid" else (1.0, 0.98, 0.90) if status_label == "Pending" else (0.98, 0.95, 0.95)
    doc.rect(page, MARGIN, y - payment_height, CONTENT_WIDTH, payment_height, fill=fill, stroke=(0.84, 0.84, 0.84))
    doc.text(page, MARGIN + 12, y - 18, "PAYMENT DETAILS", size=8, bold=True, color=(0.35, 0.35, 0.35))
    doc.text(page, MARGIN + 12, y - 38, f"Payment status: {status_label}", size=10, bold=True)
    doc.text(page, MARGIN + 190, y - 38, f"Method: {method_label}", size=9.5, bold=True)
    detail_y = y - 56
    if collected_at:
        doc.text(page, MARGIN + 12, detail_y, f"Collected: {collected_at}", size=8.2)
        detail_y -= 14
    if order.get("razorpayPaymentId"):
        doc.text(page, MARGIN + 12, detail_y, f"Gateway payment ref: {order.get('razorpayPaymentId')}", size=8.2)
    if order.get("paymentVerifiedAt"):
        doc.text(page, MARGIN + 282, detail_y, f"Verified: {readable_date(order.get('paymentVerifiedAt'))}", size=8.2)
    y -= payment_height + 20
    doc.text(page, MARGIN, y, "Thank you for shopping local with Vibe4You.", size=9.5, bold=True, color=(0.28, 0.28, 0.28))
    return y - 18


def build_receipt_pdf(order: dict[str, Any]) -> bytes:
    doc = PdfDocument()
    page = doc.new_page()
    y = _draw_brand_header(doc, page, order)
    y = _draw_order_meta(doc, page, order, y)
    y = _draw_party_blocks(doc, page, order, y)
    doc.text(page, MARGIN, y, "ITEMIZED PURCHASE", size=9, bold=True, color=(0.35, 0.35, 0.35))
    y -= 16
    y = _draw_item_header(doc, page, y)

    for item in order.get("items", []) or []:
        cells = _item_cells(item)
        wrapped = [wrap_text(value, width - 9, 7.2) for value, (_, width) in zip(cells, ITEM_COLUMNS)]
        row_height = max(30.0, 10.0 + (max(len(lines) for lines in wrapped) * 9.0))
        if y - row_height < 210:
            page, y = _new_items_page(doc, order, continuation=True)
        y = _draw_item_row(doc, page, item, y)

    _draw_totals_and_payment(doc, page, order, y - 20)
    return doc.build()
