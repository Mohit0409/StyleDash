from __future__ import annotations

import unicodedata
import sqlite3
import json
from contextlib import closing
from pathlib import Path
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

try:
    from gst_phase1_registry import (
        APPROVED_IDENTITIES, GST_RATE, HSN_CODE, POLICY_ID, RATE_EFFECTIVE_FROM,
    )
except ModuleNotFoundError:
    from scripts.gst_phase1_registry import (
        APPROVED_IDENTITIES, GST_RATE, HSN_CODE, POLICY_ID, RATE_EFFECTIVE_FROM,
    )

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
    blue = (0.07, 0.49, 0.68)
    doc.rect(page, 0, PAGE_HEIGHT - 92, PAGE_WIDTH, 92, fill=(1, 1, 1))
    doc.rect(page, 0, PAGE_HEIGHT - 96, PAGE_WIDTH, 4, fill=blue)
    doc.text(page, MARGIN, PAGE_HEIGHT - 48, "Vibe4You", size=23, bold=True, color=(0.08, 0.12, 0.16))
    doc.text(page, MARGIN, PAGE_HEIGHT - 66, "Your City. Your Shops. Your Style.", size=8.5, color=(0.34, 0.40, 0.44))
    doc.text(page, 358, PAGE_HEIGHT - 42, "CUSTOMER BILL", size=11, bold=True, color=blue)
    doc.text(page, 358, PAGE_HEIGHT - 55, "PAYMENT RECEIPT", size=8, bold=True, color=(0.23, 0.30, 0.34))
    doc.text(page, 358, PAGE_HEIGHT - 69, f"Receipt Ref: V4Y-RCP-{order.get('id', '-')}", size=7.1, color=(0.34, 0.40, 0.44))
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


def _draw_marketplace_tax_identity(doc: PdfDocument, page: list[str], y: float) -> float:
    doc.text(page, MARGIN, y, "SELLER / BILLING ENTITY", size=7.5, bold=True, color=(0.38, 0.38, 0.38))
    y -= 15
    doc.text(page, MARGIN, y, "Vibe4You | GSTIN: 23JVZPM8734E1ZT", size=8.2, bold=True)
    y -= 13
    doc.text(page, MARGIN, y, "Building No. 68, Shaktinagar Vistar, Neemuch, Madhya Pradesh - 458441", size=7.8)
    y -= 13
    doc.text(page, MARGIN, y, "Order payment summary.", size=7.2, color=(0.40, 0.44, 0.47))
    return y - 18


ITEM_COLUMNS = [
    ("Product", 173.0),
    ("HSN", 33.0),
    ("Size", 42.0),
    ("Color", 63.0),
    ("Qty", 27.0),
    ("Unit", 76.0),
    ("Line total", 101.0),
]


def _draw_item_header(doc: PdfDocument, page: list[str], y: float) -> float:
    height = 24.0
    doc.rect(page, MARGIN, y - height, CONTENT_WIDTH, height, fill=(0.07, 0.49, 0.68))
    x = MARGIN + 5
    for title, width in ITEM_COLUMNS:
        doc.text(page, x, y - 16, title.upper(), size=6.8, bold=True, color=(1, 1, 1))
        x += width
    return y - height


def _item_cells(item: dict[str, Any]) -> list[str]:
    approved_hsn = (
        _is_legacy_phase1_item(item)
        and item.get("gstPolicyId") == POLICY_ID
        and item.get("hsnCode") == HSN_CODE
        and str(item.get("gstRate")) == str(GST_RATE)
    )
    return [
        clean_pdf_text(item.get("productName") or "-"),
        HSN_CODE if approved_hsn else "",
        clean_pdf_text(item.get("size") or "-"),
        clean_pdf_text(item.get("colourName") or "-"),
        clean_pdf_text(item.get("quantity") or 0),
        money(item.get("unitPrice", 0)),
        money(item.get("lineTotal", 0)),
    ]


def _draw_item_row(doc: PdfDocument, page: list[str], item: dict[str, Any], y: float) -> float:
    cells = _item_cells(item)
    wrapped = [wrap_text(value, width - 9, 7.2)
               for value, (_, width) in zip(cells, ITEM_COLUMNS)]
    row_lines = max(len(lines) for lines in wrapped)
    row_height = max(30.0, 10.0 + (row_lines * 9.0))
    doc.rect(page, MARGIN, y - row_height, CONTENT_WIDTH, row_height, stroke=(0.88, 0.88, 0.88))
    x = MARGIN + 5
    for lines, (_, width) in zip(wrapped, ITEM_COLUMNS):
        text_y = y - 15
        for line in lines[:4]:
            if line:
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


def _receipt_amount_in_words(value: Any) -> str:
    """Display the customer's original grand total in Indian-rupee words."""
    try:
        amount = Decimal(str(value or 0)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return "Amount not available"
    if not amount.is_finite() or amount < 0 or amount >= 100000000000:
        return "Amount not available"
    small = ("Zero", "One", "Two", "Three", "Four", "Five", "Six",
             "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve",
             "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen",
             "Eighteen", "Nineteen")
    tens = ("", "", "Twenty", "Thirty", "Forty", "Fifty",
            "Sixty", "Seventy", "Eighty", "Ninety")
    def chunk(n: int) -> str:
        if n < 20:
            return small[n]
        if n < 100:
            return tens[n // 10] + (" " + small[n % 10] if n % 10 else "")
        return small[n // 100] + " Hundred" + (
            " " + chunk(n % 100) if n % 100 else ""
        )
    groups = ((10000000, "Crore"), (100000, "Lakh"),
              (1000, "Thousand"), (1, ""))
    whole = int(amount)
    paise = int((amount - whole) * 100)
    terms = []
    for divisor, suffix in groups:
        number, whole = divmod(whole, divisor)
        if number:
            terms.append(chunk(number) + (" " + suffix if suffix else ""))
    text = (" ".join(terms) if terms else "Zero") + " Rupees"
    if paise:
        text += " and " + chunk(paise) + " Paise"
    return text + " Only"


def _approved_receipt_rate(
    item: dict[str, Any], on_date: str, registry_path: Path | None
) -> Decimal | None:
    """Read a Vibe4You-admin-approved rate, never the shop-supplied GST fields.

    The private database is opened SQLite mode=ro; no schema creation,
    historical order modification, or changes to tax classification are made.
    """
    if (_is_legacy_phase1_item(item)
            and on_date >= RATE_EFFECTIVE_FROM
            and item.get("gstPolicyId") == "gst-phase1-casio-watch-9102-v1"
            and item.get("hsnCode") == "9102" and str(item.get("gstRate")) == "18"
            and str(item.get("gstEffectiveFrom")) <= on_date
            and item.get("gstApprovalDate") == "2026-10-24"):
        return Decimal("18.00")
    legacy_rate = _legacy_phase1_product_rate(item, on_date)
    if legacy_rate is not None:
        return legacy_rate
    product_id=str(item.get("productId") or "").strip()
    if registry_path is not None and product_id:
        try:
            path=Path(registry_path).resolve()
            if path.is_file():
                with closing(sqlite3.connect(path.as_uri()+"?mode=ro",uri=True,timeout=1)) as db:
                    row=db.execute(
                        "SELECT gst_rate,supply_type,effective_from,evidence "
                        "FROM tax_classifications WHERE product_id=?",
                        (product_id,),
                    ).fetchone()
                if row:
                    rate=Decimal(str(row[0]))
                    if (str(row[1])=="taxable" and str(row[2])<=on_date
                            and str(row[3]).strip() and rate.is_finite()
                            and Decimal("0")<rate<=Decimal("100")):
                        return rate
        except (sqlite3.DatabaseError,OSError,InvalidOperation,ValueError):
            return None
    # Historical V7 rendering deliberately has no name-only fallback. Product
    # IDs can be recycled, so only the immutable Phase 1 ID-and-name pair above
    # may receive the legacy rate without a private classification record.
    return None


def _is_legacy_phase1_item(item: dict[str, Any]) -> bool:
    """Accept only the immutable historical snapshot of an approved Casio."""
    product_id = str(item.get("productId") or "")
    expected = APPROVED_IDENTITIES.get(product_id)
    return bool(expected and str(item.get("productName") or "").strip() == expected[0])


def _legacy_phase1_product_rate(item: dict[str, Any], on_date: str) -> Decimal | None:
    """Return 18% only for an exact approved historical Casio line item."""
    if _is_legacy_phase1_item(item) and on_date >= RATE_EFFECTIVE_FROM:
        return GST_RATE
    return None


def _legacy_phase1_delivery_rate(items: list[dict[str, Any]], rates: list[Decimal]) -> Decimal | None:
    """Owner-directed ancillary-delivery treatment for exact 18% Casio-only orders."""
    if not items or len(items) != len(rates):
        return None
    if any(not _is_legacy_phase1_item(item) for item in items):
        return None
    if any(rate != GST_RATE for rate in rates):
        return None
    return GST_RATE


def _legacy_phase1_display_item(
    item: dict[str, Any], on_date: str, registry_path: Path | None
) -> dict[str, Any]:
    """Add display-only tax fields to a legacy order item without mutating it."""
    output = dict(item)
    if (
        not _is_legacy_phase1_item(output)
        or _approved_receipt_rate(output, on_date, registry_path) != GST_RATE
    ):
        # Never carry an unverified Phase 1 label into a customer-facing copy.
        if output.get("gstPolicyId") == POLICY_ID:
            for key in ("gstPolicyId", "hsnCode", "gstRate", "gstEffectiveFrom", "gstApprovalDate"):
                output.pop(key, None)
        return output
    output.update({
        "gstPolicyId": POLICY_ID,
        "hsnCode": HSN_CODE,
        "gstRate": str(GST_RATE),
    })
    return output


def _legacy_phase1_display_order(
    order: dict[str, Any], registry_path: Path | None
) -> dict[str, Any]:
    """Return a display copy; historical order/payment data is never rewritten."""
    result = dict(order)
    try:
        on_date = datetime.fromisoformat(
            str(order.get("createdAt") or "").replace("Z", "+00:00")
        ).date().isoformat()
    except ValueError:
        return result
    items = order.get("items")
    if isinstance(items, list):
        result["items"] = [
            _legacy_phase1_display_item(item, on_date, registry_path)
            if isinstance(item, dict) else item
            for item in items
        ]
    return result


def _receipt_item_tax_code(item: dict[str, Any]) -> str:
    """Return a display code only where the receipt renderer can verify it.

    Shop-supplied HSN text is deliberately never copied to a customer bill.
    The legacy Casio identity allowlist is the only non-database source that
    has both a pinned product identity and a verified HSN.
    """
    if (
        _is_legacy_phase1_item(item)
        and item.get("gstPolicyId") == POLICY_ID
        and item.get("hsnCode") == HSN_CODE
        and str(item.get("gstRate")) == str(GST_RATE)
    ):
        return HSN_CODE
    return ""


def _allocate_receipt_discounts(gross: list[Decimal], discount: Decimal) -> list[Decimal] | None:
    """Allocate an existing total discount exactly by largest paise remainders."""
    q=Decimal("0.01")
    if not gross or sum(gross)<=0 or discount<0 or discount>sum(gross):
        return None
    if any(n != n.quantize(q) or n<0 for n in [*gross,discount]):
        return None
    gross_paise=[int(v*100) for v in gross]
    disc_paise=int(discount*100)
    whole=[]
    fractions=[]
    for value in gross_paise:
        share=Decimal(value)*disc_paise / sum(gross_paise)
        floor=int(share)
        whole.append(floor)
        fractions.append(share-floor)
    residual=disc_paise-sum(whole)
    for i in sorted(range(len(gross)),key=lambda i:(-fractions[i],i))[:residual]:
        whole[i]+=1
    if sum(whole)!=disc_paise or any(n>v for n,v in zip(whole,gross_paise)):
        return None
    return [Decimal(n)/100 for n in whole]


def _approved_receipt_service_rate(
    component: str, order_date: str, policy_path: Path | None
) -> Decimal | None:
    """Use only a business-approved, source-documented component tax policy."""
    if policy_path is None or component not in ("delivery","try_at_home"):
        return None
    try:
        path=Path(policy_path).resolve()
        if not path.is_file() or path.stat().st_size>65536:
            return None
        config=json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(config,dict) or config.get("approved") is not True:
            return None
        if not str(config.get("approved_by") or "").strip():
            return None
        if len(str(config.get("evidence") or "").strip())<12:
            return None
        component_data=(config.get("components") or {}).get(component)
        if not isinstance(component_data,dict):
            return None
        if component_data.get("treatment")!="independently_verified":
            return None
        if component_data.get("supply_type")!="taxable":
            return None
        effective=str(component_data.get("effective_from") or "")
        if len(effective)!=10 or datetime.fromisoformat(effective).date().isoformat()!=effective:
            return None
        if effective>order_date:
            return None
        sac=str(component_data.get("sac") or "").strip()
        if not (sac.isascii() and sac.isdigit() and 4<=len(sac)<=8):
            return None
        rate=Decimal(str(component_data["gst_rate"]))
        if not rate.is_finite() or rate<=0 or rate>100:
            return None
        return rate
    except (OSError,ValueError,TypeError,KeyError,InvalidOperation):
        return None



def _approved_ancillary_goods_delivery_rate(
    order: dict[str, Any],
    order_date: str,
    items: list[dict[str, Any]],
    product_rates: list[Decimal],
    policy_path: Path | None,
) -> Decimal | None:
    """Use a narrowly approved composite-goods delivery rule, never infer it.

    Only for exact documented order references, customer totals, delivery
    charges, original sale dates and independently verified principal-goods
    rates. No blanket delivery GST rule or mixed basket assumptions.
    """
    if policy_path is None or len(items) != 1 or len(product_rates) != 1:
        return None
    order_id = str(order.get("id") or order.get("orderId") or "").strip()
    if not order_id:
        return None
    try:
        path = Path(policy_path).resolve()
        if not path.is_file() or path.stat().st_size > 65536:
            return None
        config = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(config, dict) or config.get("approved") is not True
                or not str(config.get("approved_by") or "").strip()
                or len(str(config.get("evidence") or "").strip()) < 25):
            return None
        treatment = (config.get("components") or {}).get("delivery")
        if (not isinstance(treatment, dict)
                or treatment.get("treatment") != "incidental_to_single_principal_goods_supply"
                or treatment.get("supply_type") != "taxable"):
            return None
        approvals = treatment.get("order_authorizations")
        if not isinstance(approvals, dict):
            return None
        permit = approvals.get(order_id)
        if (not isinstance(permit, dict)
                or permit.get("confirmed_as_part_of_goods_sale") is not True
                or len(str(permit.get("evidence") or "").strip()) < 20
                or str(permit.get("order_date") or "") != order_date):
            return None
        verified = product_rates[0]
        if not verified.is_finite() or verified <= 0 or verified > 100:
            return None
        approved_rate = Decimal(str(permit.get("principal_goods_gst_rate")))
        paid_total = Decimal(str(order.get("grandTotal")))
        paid_delivery = Decimal(str(order.get("deliveryFee")))
        approved_total = Decimal(str(permit.get("customer_paid_total")))
        approved_delivery = Decimal(str(permit.get("delivery_charge")))
        try_at_home = Decimal(str(order.get("tryAtHomeFee") or 0))
        values = (approved_rate, paid_total, paid_delivery, approved_total,
                  approved_delivery, try_at_home)
        if not all(v.is_finite() for v in values):
            return None
        if (approved_rate != verified or paid_total != approved_total
                or paid_delivery != approved_delivery or paid_delivery <= 0
                or try_at_home != 0):
            return None
        return verified
    except (OSError, ValueError, TypeError, KeyError, InvalidOperation):
        return None


def _verified_receipt_gst_breakdown(
    order: dict[str, Any], *, registry_path: Path | None = None,
    service_policy_path: Path | None = None
) -> dict[str, Any] | None:
    """Extract GST from original paid gross, never add it to checkout totals.

    Fail closed if any product has an unverified rate, or if separately
    charged services lack their own formally approved tax treatment.
    """
    if order.get("isPaymentTestOrder") is True or order.get("fulfillmentRequired") is False:
        return None
    items=order.get("items")
    if not isinstance(items,list) or not items or not all(isinstance(i,dict) for i in items):
        return None
    try:
        dt=datetime.fromisoformat(str(order.get("createdAt") or "").replace("Z","+00:00"))
        on_date=dt.date().isoformat()
        values={k:Decimal(str(order.get(k) or 0)) for k in (
            "subtotal", "discount", "deliveryFee", "tryAtHomeFee", "grandTotal"
        )}
        line_amounts=[Decimal(str(item.get("lineTotal"))) for item in items]
    except (ValueError,TypeError,InvalidOperation):
        return None
    if not all(v.is_finite() and v>=0 for v in [*values.values(),*line_amounts]):
        return None
    amount=values["grandTotal"]
    if amount<=0 or sum(line_amounts)!=values["subtotal"]:
        return None
    if (values["subtotal"]-values["discount"]+
            values["deliveryFee"]+values["tryAtHomeFee"]!=amount):
        return None
    allocations=_allocate_receipt_discounts(line_amounts,values["discount"])
    if allocations is None:
        return None
    # Delivery and try-at-home may require different tax treatment. No
    # default rate is inherited from the goods; verified service policy only.
    address=order.get("address") or {}
    if not isinstance(address,dict):
        return None
    place=str(address.get("state") or "").strip().casefold()
    # Historical checkout saved Madhya Pradesh without a space for one order.
    # Normalize only the verified alias, never infer a state from unknown text.
    if place == "madhyapradesh":
        place = "madhya pradesh"
    known_states={
        "madhya pradesh", "rajasthan", "maharashtra", "gujarat", "delhi",
        "uttar pradesh", "bihar", "kerala", "karnataka", "tamil nadu",
        "telangana", "andhra pradesh", "punjab", "haryana", "west bengal",
        "chhattisgarh", "odisha", "assam", "goa", "uttarakhand",
        "himachal pradesh", "jharkhand", "tripura", "manipur", "mizoram",
        "nagaland", "meghalaya", "sikkim", "arunachal pradesh",
        "jammu and kashmir", "ladakh", "puducherry", "chandigarh",
        "andaman and nicobar islands", "lakshadweep",
        "dadra and nagar haveli and daman and diu"
    }
    if place not in known_states:
        return None
    quantum=Decimal("0.01")
    gst=Decimal("0.00")
    rates=set()
    product_rates: list[Decimal] = []
    components: list[dict[str, Any]] = []
    for item,gross,discount_share in zip(items,line_amounts,allocations):
        rate=_approved_receipt_rate(item,on_date,registry_path)
        if rate is None:
            return None
        net_gross=gross-discount_share
        tax=(net_gross*rate/(Decimal("100")+rate)).quantize(
            quantum,rounding=ROUND_HALF_UP
        )
        gst+=tax
        rates.add(rate)
        product_rates.append(rate)
        components.append({
            "description": clean_pdf_text(item.get("productName") or "Product"),
            "tax_code": _receipt_item_tax_code(item),
            "gross": net_gross,
            "taxable": net_gross-tax,
            "rate": rate,
            "gst": tax,
        })
    for component,field in (("delivery","deliveryFee"),("try_at_home","tryAtHomeFee")):
        gross=values[field]
        if gross==0:
            continue
        rate=_approved_receipt_service_rate(component,on_date,service_policy_path)
        if rate is None and component == "delivery" and values["tryAtHomeFee"] == 0:
            rate = _legacy_phase1_delivery_rate(items, product_rates)
        if rate is None and component == "delivery":
            rate = _approved_ancillary_goods_delivery_rate(
                order, on_date, items, product_rates, service_policy_path
            )
        if rate is None:
            return None
        tax=(gross*rate/(Decimal("100")+rate)).quantize(
            quantum,rounding=ROUND_HALF_UP
        )
        gst+=tax
        rates.add(rate)
        components.append({
            "description": "Delivery charge" if component == "delivery" else "Try at home charge",
            # A service code is shown only if a future independently verified
            # policy carries one. The historic exact-Casio rule has no SAC.
            "tax_code": "",
            "gross": gross,
            "taxable": gross-tax,
            "rate": rate,
            "gst": tax,
        })
    taxable=amount-gst
    if not components or sum((component["taxable"] for component in components), Decimal("0.00")) != taxable:
        return None
    rate_label=(str(next(iter(rates)).normalize())+"%" if len(rates)==1
                else "mixed verified rates")
    if place=="madhya pradesh":
        cgst=(gst/2).quantize(quantum,rounding=ROUND_HALF_UP)
        sgst=gst-cgst
        if taxable+cgst+sgst!=amount:
            raise ValueError("GST-inclusive receipt total must reconcile")
        # Allocate split-tax rounding at component level while preserving the
        # authoritative aggregate exactly. This prevents a one-paise mismatch
        # between the GST table and the receipt total.
        component_cgst=[
            (component["gst"] / 2).quantize(quantum, rounding=ROUND_HALF_UP)
            for component in components
        ]
        difference=cgst-sum(component_cgst,Decimal("0.00"))
        if difference:
            steps=int(abs(difference)/quantum)
            adjustment=quantum if difference>0 else -quantum
            for index in range(steps):
                component_cgst[index % len(component_cgst)] += adjustment
        for component,component_tax in zip(components,component_cgst):
            component["cgst"]=component_tax
            component["sgst"]=component["gst"]-component_tax
        return {"rate_label":rate_label,"taxable":taxable,"gst":gst,
                "cgst":cgst,"sgst":sgst,"type":"intrastate",
                "half_rate_label":(str((next(iter(rates))/2).normalize())+"%"
                                   if len(rates)==1 else ""),
                "components":components}
    if taxable+gst!=amount:
        raise ValueError("GST-inclusive receipt total must reconcile")
    for component in components:
        component["igst"]=component["gst"]
    return {"rate_label":rate_label,"taxable":taxable,
            "gst":gst,"igst":gst,"type":"interstate","components":components}


def _draw_gst_component_header(doc: PdfDocument, page: list[str], y: float,
                               gst_breakdown: dict[str, Any], *, continuation: bool = False) -> float:
    title = "GST SUPPLY BREAKDOWN - INCLUDED IN TOTAL"
    if continuation:
        title += " (CONTINUED)"
    doc.text(page, MARGIN, y, title, size=8.1, bold=True, color=(0.07, 0.49, 0.68))
    y -= 13
    columns = [("SUPPLY", 176.0), ("HSN/SAC", 46.0), ("TAXABLE VALUE", 80.0), ("RATE", 45.0)]
    if gst_breakdown["type"] == "intrastate":
        half = gst_breakdown["half_rate_label"]
        columns += [(f"CGST {half}", 84.0), (f"SGST {half}", 84.0)]
    else:
        columns += [(f"IGST {gst_breakdown['rate_label']}", 168.0)]
    doc.rect(page, MARGIN, y - 20, CONTENT_WIDTH, 20, fill=(0.07, 0.49, 0.68))
    x = MARGIN + 5
    for heading, width in columns:
        doc.text(page, x, y - 13, heading, size=6.4, bold=True, color=(1, 1, 1))
        x += width
    return y - 20


def _draw_gst_component_table(doc: PdfDocument, page: list[str], order: dict[str, Any],
                              y: float, gst_breakdown: dict[str, Any]) -> tuple[list[str], float]:
    """Render each verified goods/service supply without altering order data."""
    if y < 330:
        page = doc.new_page()
        y = _draw_brand_header(doc, page, order)
    y = _draw_gst_component_header(doc, page, y, gst_breakdown)
    for component in gst_breakdown["components"]:
        lines = wrap_text(component["description"], 167.0, 7.0)
        row_height = max(22.0, 7.0 + (len(lines) * 8.5))
        if y - row_height < 245:
            page = doc.new_page()
            y = _draw_brand_header(doc, page, order)
            y = _draw_gst_component_header(doc, page, y, gst_breakdown, continuation=True)
        doc.rect(page, MARGIN, y-row_height, CONTENT_WIDTH, row_height, stroke=(0.86, 0.86, 0.86))
        x = MARGIN + 5
        line_y = y-13
        for line in lines[:3]:
            doc.text(page, x, line_y, line, size=7.0)
            line_y -= 8.5
        x += 176.0
        doc.text(page, x, y-13, component["tax_code"] or "-", size=7.0); x += 46.0
        doc.text(page, x, y-13, money(component["taxable"]), size=7.0); x += 80.0
        doc.text(page, x, y-13, f"{component['rate'].normalize()}%", size=7.0); x += 45.0
        if gst_breakdown["type"] == "intrastate":
            doc.text(page, x, y-13, money(component["cgst"]), size=7.0); x += 84.0
            doc.text(page, x, y-13, money(component["sgst"]), size=7.0)
        else:
            doc.text(page, x, y-13, money(component["igst"]), size=7.0)
        y -= row_height
    if y < 245:
        page = doc.new_page()
        y = _draw_brand_header(doc, page, order)
        y = _draw_gst_component_header(doc, page, y, gst_breakdown, continuation=True)
    doc.rect(page, MARGIN, y-22, CONTENT_WIDTH, 22, fill=(0.94, 0.97, 0.99), stroke=(0.76, 0.84, 0.88))
    doc.text(page, MARGIN+5, y-14, "TOTAL GST INCLUDED", size=7.0, bold=True)
    doc.text(page, MARGIN+227, y-14, money(gst_breakdown["taxable"]), size=7.0, bold=True)
    doc.text(page, MARGIN+307, y-14, gst_breakdown["rate_label"], size=7.0, bold=True)
    if gst_breakdown["type"] == "intrastate":
        doc.text(page, MARGIN+352, y-14, money(gst_breakdown["cgst"]), size=7.0, bold=True)
        doc.text(page, MARGIN+436, y-14, money(gst_breakdown["sgst"]), size=7.0, bold=True)
    else:
        doc.text(page, MARGIN+352, y-14, money(gst_breakdown["igst"]), size=7.0, bold=True)
    return page, y-34


def _draw_totals_and_payment(doc: PdfDocument, page: list[str], order: dict[str, Any], y: float,
                             *, registry_path: Path | None = None,
                             service_policy_path: Path | None = None) -> float:
    box_width = 236.0
    right_x = PAGE_WIDTH - MARGIN - box_width
    totals = [
        ("Subtotal", money(order.get("subtotal", 0))),
        ("Discount", f"- {money(order.get('discount', 0))}" if Decimal(str(order.get("discount") or 0)) > 0 else money(0)),
        ("Delivery", money(order.get("deliveryFee", 0))),
    ]
    try_fee = Decimal(str(order.get("tryAtHomeFee") or 0))
    if try_fee:
        totals.append(("Try at home", money(try_fee)))
    gst_breakdown=_verified_receipt_gst_breakdown(
        order,registry_path=registry_path,service_policy_path=service_policy_path
    )
    left_x=MARGIN
    if gst_breakdown is not None:
        page,y=_draw_gst_component_table(doc,page,order,y,gst_breakdown)
    else:
        if y < 250:
            page = doc.new_page()
            y = _draw_brand_header(doc, page, order)
        doc.text(page,left_x,y,"GST BREAKUP",size=8.0,bold=True,
                 color=(0.07,0.49,0.68))
        doc.text(page,left_x,y-17,
                 "Pending verified product/tax classification",size=7.2)
        doc.text(page,left_x,y-30,
                 "No additional tax is charged on this receipt.",size=7.1)
    if y < 250:
        page = doc.new_page()
        y = _draw_brand_header(doc, page, order)
    doc.text(page, right_x, y, "ORDER TOTAL", size=8, bold=True, color=(0.38, 0.38, 0.38))
    y -= 18
    for label, value in totals:
        doc.text(page, right_x, y, label, size=8.5)
        doc.text(page, right_x + 132, y, value, size=8.5, bold=True)
        y -= 16
    doc.line(page, right_x, y + 5, PAGE_WIDTH - MARGIN, y + 5, color=(0.40, 0.40, 0.40))
    grand_total = f"Grand Total: {money(order.get('grandTotal', 0))}"
    doc.text(page, right_x, y - 13, grand_total, size=11.5, bold=True)
    y -= 37
    doc.text(page, MARGIN, y, "Invoice Amount In Words", size=8.5, bold=True,
             color=(0.07, 0.49, 0.68))
    y -= 15
    y = _draw_wrapped(
        doc, page, MARGIN, y, _receipt_amount_in_words(order.get("grandTotal", 0)),
        CONTENT_WIDTH, size=8.1, line_height=12,
    )
    y -= 14
    # Display only the original payment state: never change grandTotal or
    # mistake an unverified COD collection for a confirmed payment.
    received = None
    if str(order.get("paymentStatus") or "").casefold() == "paid":
        received = Decimal(str(order.get("grandTotal") or 0))
    elif order.get("codAdvancePaid") is True:
        received = Decimal(str(order.get("codAdvanceAmount") or 0))
    if received is not None:
        total_amount = Decimal(str(order.get("grandTotal") or 0))
        received = max(Decimal("0"), min(received, total_amount))
        doc.text(page, right_x, y, f"Received: {money(received)}", size=8.6)
        doc.text(page, right_x, y - 15,
                 f"Balance: {money(total_amount - received)}", size=8.6)
    else:
        doc.text(page, right_x, y, "Received / Balance: Not verified", size=8)
    y -= 43
    status_label, method_label, collected_at = _payment_labels(order)
    payment_details: list[str] = []
    if str(order.get("paymentMethod") or "").casefold() == "cod" and order.get("codAdvancePaid"):
        payment_details.append(f"Online booking payment: {money(order.get('codAdvanceAmount', 0))}")
        if isinstance(order.get("codAmountCollected"), (int, float, Decimal)):
            payment_details.append(f"COD balance collected at delivery: {money(order['codAmountCollected'])}")
        else:
            payment_details.append(f"COD balance due at delivery: {money(order.get('codAmountDue', 0))}")
    if collected_at:
        payment_details.append(f"Collected: {collected_at}")
    if order.get("razorpayPaymentId"):
        payment_details.append(f"Gateway payment ref: {order.get('razorpayPaymentId')}")
    if order.get("paymentVerifiedAt"):
        payment_details.append(f"Verified: {readable_date(order.get('paymentVerifiedAt'))}")
    payment_height = max(76.0, 52.0 + (14.0 * len(payment_details)))
    if y - payment_height < 42:
        page = doc.new_page()
        y = _draw_brand_header(doc, page, order)
    fill = (0.94, 0.98, 0.91) if status_label == "Paid" else (1.0, 0.98, 0.90) if status_label == "Pending" else (0.98, 0.95, 0.95)
    doc.rect(page, MARGIN, y - payment_height, CONTENT_WIDTH, payment_height, fill=fill, stroke=(0.84, 0.84, 0.84))
    doc.text(page, MARGIN + 12, y - 18, "PAYMENT DETAILS", size=8, bold=True, color=(0.35, 0.35, 0.35))
    doc.text(page, MARGIN + 12, y - 38, f"Payment status: {status_label}", size=10, bold=True)
    doc.text(page, MARGIN + 190, y - 38, f"Method: {method_label}", size=9.5, bold=True)
    detail_y = y - 56
    for detail in payment_details:
        doc.text(page, MARGIN + 12, detail_y, detail, size=8.2)
        detail_y -= 14
    y -= payment_height + 20
    doc.text(page, MARGIN, y, "Thank you for shopping local with Vibe4You.", size=9.5,
             bold=True, color=(0.28, 0.28, 0.28))
    doc.text(page, PAGE_WIDTH - MARGIN - 165, y - 18, "For: Vibe4You",
             size=8.4, bold=True)
    doc.text(page, PAGE_WIDTH - MARGIN - 165, y - 30, "Authorized Signatory",
             size=7.4)
    return y - 42


def build_receipt_pdf(order: dict[str, Any], *,
                      registry_path: Path | None = None,
                      service_policy_path: Path | None = None) -> bytes:
    order = _legacy_phase1_display_order(order, registry_path)
    doc = PdfDocument()
    page = doc.new_page()
    y = _draw_brand_header(doc, page, order)
    y = _draw_order_meta(doc, page, order, y)
    y = _draw_party_blocks(doc, page, order, y)
    y = _draw_marketplace_tax_identity(doc, page, y)
    doc.text(page, MARGIN, y, "ITEMIZED PURCHASE", size=9, bold=True, color=(0.35, 0.35, 0.35))
    y -= 16
    y = _draw_item_header(doc, page, y)

    for item in order.get("items", []) or []:
        cells = _item_cells(item)
        wrapped = [[""] if column == 1 else wrap_text(value, width - 9, 7.2)
               for column, (value, (_, width)) in enumerate(zip(cells, ITEM_COLUMNS))]
        row_height = max(30.0, 10.0 + (max(len(lines) for lines in wrapped) * 9.0))
        if y - row_height < 210:
            page, y = _new_items_page(doc, order, continuation=True)
        y = _draw_item_row(doc, page, item, y)

    _draw_totals_and_payment(
        doc,page,order,y-20,registry_path=registry_path,
        service_policy_path=service_policy_path
    )
    return doc.build()
