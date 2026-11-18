"""Private Vibe4You principal-reseller GST classification registry.

Shop/seller-submitted tax metadata is not trusted. Only the marketplace admin
can approve SKU classifications using documented evidence. Database is separate
from orders and shop settlement data.
"""
from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

try:
    from gst_invoice_draft import InvoiceDraftError
except ModuleNotFoundError:
    from scripts.gst_invoice_draft import InvoiceDraftError


class TaxClassificationRegistry:
    def __init__(self, data_dir: Path | str):
        self.path=Path(data_dir)/"vibe4you-tax-classifications.sqlite3"
        self.path.parent.mkdir(parents=True,exist_ok=True)

    @contextmanager
    def _db(self):
        con=sqlite3.connect(self.path,timeout=20)
        try:
            con.row_factory=sqlite3.Row
            yield con
            con.commit()
        finally:
            con.close()

    def _create(self,con):
        con.executescript("""
            CREATE TABLE IF NOT EXISTS tax_classifications(
                product_id TEXT PRIMARY KEY,
                hsn_code TEXT NOT NULL,
                gst_rate TEXT NOT NULL,
                supply_type TEXT NOT NULL,
                evidence TEXT NOT NULL,
                effective_from TEXT NOT NULL,
                approved_by TEXT NOT NULL,
                approved_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS classification_audit(
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL,
                before_json TEXT,
                after_json TEXT NOT NULL,
                approved_by TEXT NOT NULL,
                changed_at TEXT NOT NULL
            );
        """)

    @staticmethod
    def _validate(product_id: Any, hsn: Any, rate: Any, supply_type: Any,
                  evidence: Any, effective_from: Any, approved_by: Any) -> dict[str,str]:
        pid=str(product_id or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{3,128}",pid):
            raise InvoiceDraftError("Invalid product id for tax classification")
        hsn=str(hsn or "").strip()
        # HSN is optional on eligible B2C invoices with preceding-year AATO
        # not exceeding INR 5 crore. GST rate/evidence are still mandatory.
        # Invoice issuance separately blocks missing HSN for B2B or higher AATO.
        if hsn and not re.fullmatch(r"[0-9]{2,8}",hsn):
            raise InvoiceDraftError("HSN must be 2 to 8 digits if provided")
        try:
            amount=Decimal(str(rate))
        except (InvalidOperation,TypeError):
            raise InvoiceDraftError("GST rate must be verified") from None
        if not amount.is_finite() or amount<0 or amount>100 or amount.as_tuple().exponent < -2:
            raise InvoiceDraftError("GST rate is invalid")
        if supply_type not in ("taxable","exempt","nil_rated","zero_rated"):
            raise InvoiceDraftError("Supply type must be verified")
        if supply_type=="taxable" and amount<=0:
            raise InvoiceDraftError("Taxable supply must use verified positive GST rate")
        if supply_type!="taxable" and amount!=0:
            raise InvoiceDraftError("Non-taxable supply cannot use positive GST rate")
        if not isinstance(evidence,str) or len(evidence.strip())<12:
            raise InvoiceDraftError("Document official tax-classification source")
        try:
            date.fromisoformat(str(effective_from))
        except ValueError:
            raise InvoiceDraftError("GST effective date must be YYYY-MM-DD") from None
        if not isinstance(approved_by,str) or not approved_by.strip():
            raise InvoiceDraftError("Approving administrator required")
        return {
            "product_id":pid,"hsn_code":hsn,"gst_rate":str(amount),
            "supply_type":str(supply_type),"evidence":evidence.strip()[:1200],
            "effective_from":str(effective_from),"approved_by":approved_by.strip(),
            "approved_at":datetime.now(timezone.utc).isoformat()
        }

    def approve(self, *, product_id: str, hsn_code: str, gst_rate: str,
                supply_type: str, evidence: str, effective_from: str,
                approved_by: str) -> dict[str,str]:
        record=self._validate(product_id,hsn_code,gst_rate,supply_type,evidence,effective_from,approved_by)
        import json
        with self._db() as con:
            self._create(con)
            before=con.execute(
                "SELECT * FROM tax_classifications WHERE product_id=?",
                (record["product_id"],)
            ).fetchone()
            con.execute(
                "INSERT INTO tax_classifications(product_id,hsn_code,gst_rate,supply_type,evidence,"
                "effective_from,approved_by,approved_at) VALUES(?,?,?,?,?,?,?,?) "
                "ON CONFLICT(product_id) DO UPDATE SET "
                "hsn_code=excluded.hsn_code,gst_rate=excluded.gst_rate,"
                "supply_type=excluded.supply_type,evidence=excluded.evidence,"
                "effective_from=excluded.effective_from,approved_by=excluded.approved_by,"
                "approved_at=excluded.approved_at",
                tuple(record.values())
            )
            con.execute(
                "INSERT INTO classification_audit("
                "product_id,before_json,after_json,approved_by,changed_at) VALUES(?,?,?,?,?)",
                (record["product_id"],json.dumps(dict(before)) if before else None,
                 json.dumps(record),approved_by,record["approved_at"])
            )
        return record

    def get(self, product_id: str, *, as_of: date | None = None) -> dict[str,str] | None:
        if not self.path.is_file(): return None
        with self._db() as con:
            self._create(con)
            row=con.execute("SELECT * FROM tax_classifications WHERE product_id=?",
                            (product_id,)).fetchone()
            if row is None:return None
            result=dict(row)
            if date.fromisoformat(result["effective_from"]) > (as_of or date.today()):
                return None
            return result

    def list_recent(self, limit: int=250) -> list[dict[str,str]]:
        if not self.path.is_file(): return []
        with self._db() as con:
            self._create(con)
            return [dict(row) for row in con.execute(
                "SELECT * FROM tax_classifications ORDER BY approved_at DESC LIMIT ?",
                (max(1,min(int(limit),500)),)
            )]
