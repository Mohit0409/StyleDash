from __future__ import annotations

import re
import unittest

from scripts.receipt_pdf import build_receipt_pdf, clean_pdf_text


def delivered_order(**overrides):
    order = {
        "id": "V4Y-20260904-ABC123",
        "status": "delivered",
        "createdAt": "2026-09-04T10:00:00+00:00",
        "updatedAt": "2026-09-04T14:30:00+00:00",
        "paymentMethod": "cod",
        "paymentStatus": "pending",
        "subtotal": 980,
        "discount": 80,
        "deliveryFee": 40,
        "taxes": 10,
        "grandTotal": 950,
        "address": {
            "name": "Asha Sharma",
            "phone": "9999999999",
            "street": "14, Station Road",
            "city": "Neemuch",
            "state": "Madhya Pradesh",
            "pincode": "458441",
        },
        "items": [{
            "storeName": "Nakoda Jewellery",
            "productName": "Women’s Co-ord Set – Rose",
            "size": "M",
            "colourName": "Rose Gold",
            "quantity": 2,
            "unitPrice": 490,
            "lineTotal": 980,
        }],
    }
    order.update(overrides)
    return order


class ReceiptPdfTests(unittest.TestCase):
    def test_professional_receipt_contains_branding_table_totals_and_readable_dates(self):
        pdf = build_receipt_pdf(delivered_order())
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertIn(b"Vibe4You", pdf)
        self.assertIn(b"RECEIPT / INVOICE", pdf)
        self.assertIn(b"Receipt Ref: V4Y-RCP-V4Y-20260904-ABC123", pdf)
        self.assertIn(b"04 Sep 2026, 03:30 PM IST", pdf)
        for heading in (b"STORE", b"PRODUCT", b"SIZE", b"COLOR", b"QTY", b"UNIT", b"LINE TOTAL"):
            self.assertIn(heading, pdf)
        self.assertIn(b"Grand Total: INR 950.00", pdf)

    def test_problematic_product_punctuation_is_cleaned_without_question_mark_replacement(self):
        self.assertEqual(clean_pdf_text("Women’s Co-ord Set – Rose"), "Women's Co-ord Set - Rose")
        pdf = build_receipt_pdf(delivered_order())
        self.assertIn(b"Women's Co-ord Set - Rose", pdf)
        self.assertNotIn(b"Women?s", pdf)
        self.assertNotIn("�".encode("utf-8"), pdf)

    def test_cod_pending_receipt_uses_authoritative_pending_state(self):
        pdf = build_receipt_pdf(delivered_order(paymentStatus="pending"))
        self.assertIn(b"Payment status: Pending", pdf)
        self.assertIn(b"Method: Pay on Delivery", pdf)
        self.assertNotIn(b"Method: Cash", pdf)
        self.assertNotIn(b"Method: UPI at Delivery", pdf)

    def test_cod_collected_receipt_uses_dev1_collection_fields(self):
        pdf = build_receipt_pdf(delivered_order(
            paymentStatus="paid",
            paymentCollectionMethod="upi_at_delivery",
            paymentCollectedAt="2026-09-04T14:00:00+00:00",
        ))
        self.assertIn(b"Payment status: Paid", pdf)
        self.assertIn(b"Method: UPI at Delivery", pdf)
        self.assertIn(b"Collected: 04 Sep 2026, 07:30 PM IST", pdf)

    def test_online_paid_receipt_uses_gateway_fields_without_cod_collection_data(self):
        pdf = build_receipt_pdf(delivered_order(
            paymentMethod="upi",
            paymentStatus="paid",
            razorpayPaymentId="pay_test_123",
            paymentVerifiedAt="2026-09-04T10:05:00+00:00",
        ))
        self.assertIn(b"Payment status: Paid", pdf)
        self.assertIn(b"Method: UPI via Razorpay", pdf)
        self.assertIn(b"Gateway payment ref: pay_test_123", pdf)
        self.assertIn(b"Verified: 04 Sep 2026, 03:35 PM IST", pdf)

    def test_long_receipt_creates_multiple_printable_pages(self):
        items = []
        for index in range(24):
            items.append({
                "storeName": f"Local Store {index % 3}",
                "productName": f"Long Product Name {index} With Details",
                "size": "XL", "colourName": "Midnight Blue",
                "quantity": 1, "unitPrice": 199, "lineTotal": 199,
            })
        pdf = build_receipt_pdf(delivered_order(items=items, subtotal=4776, grandTotal=4776))
        page_count = re.search(br"/Count (\d+)", pdf)
        self.assertIsNotNone(page_count)
        count = int(page_count.group(1))
        self.assertGreaterEqual(count, 2)
        self.assertIn(b"ITEMS - CONTINUED", pdf)
        self.assertIn(f"Page 1 of {count}".encode(), pdf)
        self.assertIn(f"Page {count} of {count}".encode(), pdf)


if __name__ == "__main__":
    unittest.main()
