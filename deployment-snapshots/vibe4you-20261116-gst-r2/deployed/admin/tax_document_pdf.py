"""Vyapar-inspired A4 tax invoice/credit note layout for Vibe4You.

A representation of an ALREADY issued immutable ledger snapshot. This module
cannot issue an invoice, select a GST rate or change customer price.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

try:
    from receipt_pdf import (
        CONTENT_WIDTH, MARGIN, PAGE_HEIGHT, PAGE_WIDTH, PdfDocument,
        clean_pdf_text, money, wrap_text,
    )
    from gst_invoice_draft import InvoiceDraftError
except ModuleNotFoundError:
    from scripts.receipt_pdf import (
        CONTENT_WIDTH, MARGIN, PAGE_HEIGHT, PAGE_WIDTH, PdfDocument,
        clean_pdf_text, money, wrap_text,
    )
    from scripts.gst_invoice_draft import InvoiceDraftError


BLUE = (0.07, 0.49, 0.68)
PALE = (0.93, 0.96, 0.98)
INK = (0.08, 0.11, 0.14)
MUTED = (0.35, 0.40, 0.44)
WHITE = (1.0, 1.0, 1.0)
PENNY = Decimal("0.01")

# Sum must equal CONTENT_WIDTH=515. HSN cells may be empty for eligible B2C.
COLUMNS = [
    ("#", 19), ("Item Name", 145), ("HSN/SAC", 46), ("Qty", 29),
    ("Unit", 32), ("Price/Unit", 67), ("Discount", 63),
    ("GST", 59), ("Amount", 55),
]


def _d(value) -> Decimal:
    result = Decimal(str(value if value is not None else 0))
    if not result.is_finite():
        raise InvoiceDraftError("Invoice amount must be finite")
    return result.quantize(PENNY)


def _words_999(number: int) -> str:
    small = (
        "Zero", "One", "Two", "Three", "Four", "Five", "Six",
        "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve",
        "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen",
        "Eighteen", "Nineteen",
    )
    tens = ("", "", "Twenty", "Thirty", "Forty", "Fifty",
            "Sixty", "Seventy", "Eighty", "Ninety")
    if number < 20:
        return small[number]
    if number < 100:
        return tens[number // 10] + (" " + small[number % 10] if number % 10 else "")
    return small[number // 100] + " Hundred" + (
        " " + _words_999(number % 100) if number % 100 else ""
    )


def amount_in_words(value) -> str:
    """Indian number groups; large unsupported amounts fail without guessing."""
    rupees = _d(value)
    if rupees < 0 or rupees >= Decimal("100000000000"):
        raise InvoiceDraftError("Invoice total is outside supported words range")
    whole = int(rupees)
    paise = int((rupees - Decimal(whole)) * 100)
    groups = (
        (10000000, "Crore"), (100000, "Lakh"),
        (1000, "Thousand"), (1, ""),
    )
    fragments = []
    remaining = whole
    for divisor, name in groups:
        unit, remaining = divmod(remaining, divisor)
        if unit:
            fragments.append(_words_999(unit) + (" " + name if name else ""))
    words = " ".join(fragments) if fragments else "Zero"
    words += " Rupees"
    if paise:
        words += " and " + _words_999(paise) + " Paise"
    return words + " Only"


def _text(doc, page, x, y, value, *, size=8, bold=False, color=INK):
    doc.text(page, x, y, value, size=size, bold=bold, color=color)


def _wrap(doc, page, x, y, value, width, *, size=7.8, step=11):
    if not clean_pdf_text(value):
        return y
    for line in wrap_text(value, width, size):
        _text(doc, page, x, y, line, size=size)
        y -= step
    return y


def _right(doc, page, x_right, y, value, *, size=8, bold=False, color=INK):
    # PdfDocument text() is left-aligned, so approximate Helvetica visual width.
    text = clean_pdf_text(value)
    estimate = sum(0.54 if ch not in "il.,|!:;1 " else 0.28 for ch in text) * size
    _text(doc, page, max(MARGIN, x_right - estimate), y, text,
          size=size, bold=bold, color=color)


def _header(doc, page, document, *, continued=False):
    seller = document["seller"]
    title = "TAX INVOICE" if document["document_kind"] == "TAX_INVOICE" else "CREDIT NOTE"
    _text(doc, page, MARGIN, 793, "Vibe4You", size=19, bold=True)
    _text(doc, page, MARGIN, 775, "Supplier: Vibe4You", size=8)
    address = f"{seller['address']}, {seller['pincode']}"
    _wrap(doc, page, MARGIN, 762, address, 340, size=7.8, step=12)
    _text(doc, page, MARGIN, 726, f"GSTIN: {seller['gstin']}", size=8)
    _text(doc, page, MARGIN, 713, "State: 23 - Madhya Pradesh", size=7.6)
    _right(doc, page, PAGE_WIDTH - MARGIN, 781, "VIBE4YOU", size=13, bold=True, color=BLUE)
    _right(doc, page, PAGE_WIDTH - MARGIN, 767,
           "Your City. Your Shops. Your Style.", size=7, color=MUTED)
    doc.line(page, MARGIN, 699, PAGE_WIDTH-MARGIN, 699, color=BLUE, width=1.1)
    _text(doc, page, 230, 675,
          title + (" - CONTINUED" if continued else ""), size=13, bold=True, color=BLUE)
    return 655


def _parties(doc, page, document, y):
    customer = document["customer_address"]
    _text(doc, page, MARGIN, y, "Bill To", size=8.5, bold=True)
    _text(doc, page, MARGIN, y-16, customer.get("name") or "-", size=9, bold=True)
    address = " ".join(clean_pdf_text(customer.get(key) or "") for key in
                       ("street", "city", "state", "pincode"))
    _wrap(doc, page, MARGIN, y-30, address, 300, size=7.8, step=10)
    if document.get("recipient_gstin"):
        _text(doc, page, MARGIN, y-58,
              f"Recipient GSTIN: {document['recipient_gstin']}", size=7.3)
    _right(doc, page, PAGE_WIDTH-MARGIN, y, "Invoice Details", size=8.5, bold=True)
    number = document.get("invoice_number") or document.get("number")
    _right(doc, page, PAGE_WIDTH-MARGIN, y-16, f"Invoice No.: {number}", size=7.5)
    _right(doc, page, PAGE_WIDTH-MARGIN, y-29, f"Date: {document['issue_date']}", size=7.5)
    _right(doc, page, PAGE_WIDTH-MARGIN, y-42,
           f"Place of Supply: {document['place_of_supply_state_code']} - "
           f"{document['place_of_supply_state']}", size=7.1)
    _text(doc, page, MARGIN, y-73, f"Order Ref.: {document['order_id']}", size=7.2)
    if document["document_kind"] == "CREDIT_NOTE":
        _text(doc, page, MARGIN, y-87,
              f"Against tax invoice: {document['linked_invoice']}", size=7.2)
        _text(doc, page, MARGIN, y-100,
              f"Reason: {clean_pdf_text(document['reason'])}", size=7.2)
        return y-117
    return y-91


def _row_data(document):
    hide_hsn = document.get("hsn_optional_for_b2c") is True
    lines = document["items"] if document["document_kind"]=="TAX_INVOICE" else document["credited_lines"]
    for i, source in enumerate(lines, 1):
        is_credit = document["document_kind"] != "TAX_INVOICE"
        qty = int(source.get("quantity", 1)) if not is_credit else 1
        post = _d(source["gross"])
        pre = _d(source.get("pre_discount_gross",post))
        discount = _d(source.get("discount_amount",0))
        if pre - discount != post or qty < 1:
            raise InvoiceDraftError("Invoice line does not reconcile to billed gross")
        yield {
            "index": i, "name":clean_pdf_text(source["product_name"]),
            "hsn":"" if hide_hsn else clean_pdf_text(source.get("hsn") or ""),
            "qty":qty,
            "unit":clean_pdf_text(source.get("unit","Pcs")) if not is_credit else "Credit",
            "unit_price":(pre / qty).quantize(PENNY,rounding=ROUND_HALF_UP),
            "discount":discount, "rate":_d(source["gst_rate"]),
            "gst":_d(source["tax"]), "gross":post, "pre_gross":pre,
        }


def _table_header(doc,page,y):
    doc.rect(page,MARGIN,y-26,CONTENT_WIDTH,26,fill=BLUE)
    x=MARGIN+3
    for label,width in COLUMNS:
        _text(doc,page,x,y-17,label,size=6.45,bold=True,color=WHITE)
        x+=width
    return y-26


def _row_height(data):
    name_lines=wrap_text(data["name"],COLUMNS[1][1]-8,7.4)
    return max(39,18+10*len(name_lines))


def _draw_row(doc,page,y,data):
    x=MARGIN+3
    rate_text=f"{data['rate']:g}%"
    columns = [
        str(data["index"]),data["name"],data["hsn"],str(data["qty"]),
        data["unit"],money(data["unit_price"]),money(data["discount"]),
        money(data["gst"]),money(data["gross"]),
    ]
    height=_row_height(data)
    for j,(value,(_,width)) in enumerate(zip(columns,COLUMNS)):
        if j==2 and not value:
            pass  # actually blank HSN, not a placeholder dash
        elif j==1:
            _wrap(doc,page,x,y-14,value,width-8,size=7.25,step=10)
        else:
            _text(doc,page,x,y-14,value,size=6.4,bold=(j==8))
        if j==7:
            _text(doc,page,x,y-26,f"({rate_text})",size=6.1,color=MUTED)
        x+=width
    doc.line(page,MARGIN,y-height,PAGE_WIDTH-MARGIN,y-height,color=(0.79,0.83,0.86))
    return y-height


def _received(document, total):
    if document.get("payment_status")=="paid":
        return total
    if document.get("cod_advance_paid") is True:
        return max(Decimal("0.00"),min(total,_d(document.get("cod_advance_amount"))))
    return None


def _summary(doc,page,document,y,data):
    grand=_d(document["gross_total"])
    taxable=_d(document["taxable_total"])
    tax=_d(document["gst_total"])
    if taxable+tax != grand:
        raise InvoiceDraftError("Invoice GST totals do not reconcile")
    pretax_total=sum((row["pre_gross"] for row in data),Decimal("0.00"))
    discount=sum((row["discount"] for row in data),Decimal("0.00"))
    if pretax_total-discount != grand:
        raise InvoiceDraftError("Pre-discount totals do not reconcile to customer paid amount")
    y-=26
    _text(doc,page,MARGIN,y,"Invoice Amount In Words",size=8.4,bold=True)
    words=amount_in_words(grand)
    _wrap(doc,page,MARGIN,y-19,words,257,size=7.3,step=12)
    x=320
    lines=[
        ("Sub Total (GST incl.)",pretax_total),
        ("Discount",discount),
        ("Taxable Value",taxable),
    ]
    if document["interstate"]:
        lines.append(("IGST (included)",tax))
    else:
        if document["document_kind"]=="TAX_INVOICE":
            cgst,sgst=_d(document["cgst"]),_d(document["sgst"])
        else:
            cgst=(tax/2).quantize(PENNY,rounding=ROUND_HALF_UP)
            sgst=tax-cgst
        if cgst+sgst!=tax:raise InvoiceDraftError("CGST/SGST do not reconcile")
        lines.extend([("SGST (included)",sgst),("CGST (included)",cgst)])
    lines.append(("Round off",Decimal("0.00")))
    for key,value in lines:
        _text(doc,page,x,y,key,size=7.9)
        _right(doc,page,PAGE_WIDTH-MARGIN-2,y,money(value),size=7.7)
        y-=20
    bar=y-3
    doc.rect(page,x-3,bar-10,PAGE_WIDTH-MARGIN-x+3,25,fill=BLUE)
    _text(doc,page,x,bar-1,"Total",size=9,bold=True,color=WHITE)
    _right(doc,page,PAGE_WIDTH-MARGIN-2,bar-1,money(grand),size=8.7,bold=True,color=WHITE)
    y=bar-30
    if document["document_kind"]=="TAX_INVOICE":
        paid=_received(document,grand)
        _text(doc,page,x,y,"Received",size=7.9)
        _right(doc,page,PAGE_WIDTH-MARGIN-2,y,
               money(paid) if paid is not None else "Pending / not verified",size=7.0)
        y-=20
        _text(doc,page,x,y,"Balance",size=7.9)
        _right(doc,page,PAGE_WIDTH-MARGIN-2,y,
               money(grand-paid) if paid is not None else "Not verified",size=7.0)
        y-=20
    doc.line(page,x-3,y-7,PAGE_WIDTH-MARGIN,y-7,color=(0.78,0.82,0.86))
    y-=29
    _right(doc,page,PAGE_WIDTH-MARGIN,y,"For: Vibe4You",size=8.0,bold=True)
    signatory=clean_pdf_text(document.get("authorised_signatory") or "")
    _right(doc,page,PAGE_WIDTH-MARGIN,y-43,"Vibe4You",size=7.6)
    _right(doc,page,PAGE_WIDTH-MARGIN,y-56,"Authorized Signatory",size=8,bold=True)
    _text(doc,page,MARGIN,max(55,y-10),
          "GST is included in the amounts above; not added again.",size=7.1,color=MUTED)


def render_issued_tax_document_pdf(document: dict) -> bytes:
    """Render existing issued invoice/credit-note, with no issuance side effects."""
    kind=document.get("document_kind")
    if document.get("status")!="ISSUED" or kind not in ("TAX_INVOICE","CREDIT_NOTE"):
        raise InvoiceDraftError("Only verified immutable issued documents may be rendered")
    if document.get("address_pending_verification"):
        raise InvoiceDraftError("Registered address has not been verified")
    if document.get("hsn_optional_for_b2c") is True and document.get("recipient_gstin"):
        raise InvoiceDraftError("HSN omission cannot be applied to B2B invoice")
    if not document.get("seller",{}).get("gstin"):
        raise InvoiceDraftError("GST-registered seller is missing")
    data=list(_row_data(document))
    if not data:
        raise InvoiceDraftError("No invoice lines supplied")
    if sum((r["gross"] for r in data),Decimal("0")) != _d(document["gross_total"]):
        raise InvoiceDraftError("Invoice item sum does not equal grand total")

    pdf=PdfDocument()
    page=pdf.new_page()
    _header(pdf,page,document)
    y=_parties(pdf,page,document,655)
    y=_table_header(pdf,page,y)
    for item in data:
        height=_row_height(item)
        if y-height < 310:
            page=pdf.new_page()
            _header(pdf,page,document,continued=True)
            y=_table_header(pdf,page,648)
        y=_draw_row(pdf,page,y,item)
    if y < 330:
        page=pdf.new_page()
        _header(pdf,page,document,continued=True)
        y=650
    _summary(pdf,page,document,y,data)
    return pdf.build()
