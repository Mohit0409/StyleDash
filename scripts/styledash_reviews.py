from __future__ import annotations

import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from styledash_security import SecurityError, clean_text
except ModuleNotFoundError:
    from scripts.styledash_security import SecurityError, clean_text

REVIEWABLE_ORDER_STATUSES = {"delivered", "return_requested", "returned"}
REVIEW_SORTS = {"newest", "highest", "lowest"}


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        result = super().__exit__(exc_type, exc_value, traceback)
        self.close()
        return result


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ReviewWorkflow:
    """Verified product reviews backed by the customer SQLite database."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=5, factory=ClosingConnection)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=5000")
        return db

    def _migrate(self) -> None:
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS review_schema_migrations(
                  version INTEGER PRIMARY KEY,
                  applied_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS product_reviews(
                  id TEXT PRIMARY KEY,
                  product_id TEXT NOT NULL,
                  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                  order_id TEXT NOT NULL,
                  rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
                  title TEXT,
                  comment TEXT NOT NULL,
                  status TEXT NOT NULL DEFAULT 'published'
                    CHECK(status IN ('published','hidden')),
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  UNIQUE(user_id, product_id)
                );
                CREATE INDEX IF NOT EXISTS product_reviews_product_idx
                  ON product_reviews(product_id, status, created_at DESC);
                CREATE INDEX IF NOT EXISTS product_reviews_user_idx
                  ON product_reviews(user_id, created_at DESC);
                """
            )
            db.execute(
                "INSERT OR IGNORE INTO review_schema_migrations(version,applied_at) VALUES(1,?)",
                (_now(),),
            )
            db.commit()

    @staticmethod
    def _product_id(value: Any) -> str:
        if not isinstance(value, str):
            raise SecurityError(400, "Invalid product.", "invalid_product")
        product_id = value.strip()
        if not product_id or len(product_id) > 128 or "/" in product_id:
            raise SecurityError(400, "Invalid product.", "invalid_product")
        return product_id

    @staticmethod
    def _rating(value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
            raise SecurityError(400, "Choose a rating from 1 to 5 stars.", "invalid_rating")
        return value

    @staticmethod
    def _title(value: Any) -> str | None:
        if value in (None, ""):
            return None
        return clean_text(value, "review title", 2, 80)

    @staticmethod
    def _comment(value: Any) -> str:
        return clean_text(value, "review comment", 3, 1000)

    @staticmethod
    def _display_name(name: Any) -> str:
        parts = str(name or "Vibe4You customer").strip().split()
        if not parts:
            return "Vibe4You customer"
        if len(parts) == 1:
            return parts[0][:40]
        return f"{parts[0][:30]} {parts[-1][0].upper()}."

    def _public_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "productId": row["product_id"],
            "userName": self._display_name(row["user_name"]),
            "rating": row["rating"],
            "title": row["title"],
            "comment": row["comment"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "verifiedPurchase": True,
        }

    def _owned_row(self, review_id: str, user_id: str) -> sqlite3.Row:
        if not isinstance(review_id, str) or not review_id or len(review_id) > 64:
            raise SecurityError(404, "Review not found.", "review_not_found")
        with self.connect() as db:
            row = db.execute(
                """SELECT r.*,u.name AS user_name FROM product_reviews r
                   JOIN users u ON u.id=r.user_id
                   WHERE r.id=? AND r.user_id=?""",
                (review_id, user_id),
            ).fetchone()
        if row is None:
            raise SecurityError(404, "Review not found.", "review_not_found")
        return row

    def _qualifying_order(self, payment_store: Any, user_id: str, product_id: str) -> dict[str, Any] | None:
        with payment_store.lock:
            orders = list(payment_store.state.get("orders", {}).values())
        eligible = []
        for order in orders:
            if order.get("userId") != user_id or order.get("status") not in REVIEWABLE_ORDER_STATUSES:
                continue
            if order.get("isPaymentTestOrder") or order.get("fulfillmentRequired") is False:
                continue
            if any(item.get("productId") == product_id for item in order.get("items", [])):
                eligible.append(order)
        return max(eligible, key=lambda order: order.get("updatedAt") or order.get("createdAt") or "", default=None)

    def summaries(self, product_ids: list[str]) -> dict[str, dict[str, Any]]:
        unique: list[str] = []
        for value in product_ids:
            product_id = self._product_id(value)
            if product_id not in unique:
                unique.append(product_id)
        if not unique or len(unique) > 64:
            raise SecurityError(400, "Invalid product selection.", "invalid_product")
        placeholders = ",".join("?" for _ in unique)
        with self.connect() as db:
            rows = db.execute(
                f"""SELECT product_id,COUNT(*) AS review_count,AVG(rating) AS average_rating
                    FROM product_reviews
                    WHERE status='published' AND product_id IN ({placeholders})
                    GROUP BY product_id""",
                unique,
            ).fetchall()
        result = {product_id: {"rating": 0, "reviewCount": 0} for product_id in unique}
        for row in rows:
            result[row["product_id"]] = {
                "rating": round(float(row["average_rating"]), 1),
                "reviewCount": int(row["review_count"]),
            }
        return result

    def list_product(self, product_id: str, sort: str = "newest") -> dict[str, Any]:
        product_id = self._product_id(product_id)
        if sort not in REVIEW_SORTS:
            raise SecurityError(400, "Invalid review sort.", "invalid_review_sort")
        ordering = {
            "newest": "r.created_at DESC",
            "highest": "r.rating DESC,r.created_at DESC",
            "lowest": "r.rating ASC,r.created_at DESC",
        }[sort]
        with self.connect() as db:
            stats = db.execute(
                """SELECT COUNT(*) AS review_count,AVG(rating) AS average_rating
                   FROM product_reviews WHERE product_id=? AND status='published'""",
                (product_id,),
            ).fetchone()
            distribution_rows = db.execute(
                """SELECT rating,COUNT(*) AS review_count FROM product_reviews
                   WHERE product_id=? AND status='published' GROUP BY rating""",
                (product_id,),
            ).fetchall()
            rows = db.execute(
                f"""SELECT r.*,u.name AS user_name FROM product_reviews r
                    JOIN users u ON u.id=r.user_id
                    WHERE r.product_id=? AND r.status='published'
                    ORDER BY {ordering} LIMIT 100""",
                (product_id,),
            ).fetchall()
        reviews = [self._public_row(row) for row in rows]
        count = int(stats["review_count"] or 0)
        rating = round(float(stats["average_rating"]), 1) if count else 0
        distribution = {str(stars): 0 for stars in range(5, 0, -1)}
        for row in distribution_rows:
            distribution[str(row["rating"])] = int(row["review_count"])
        return {
            "productId": product_id,
            "rating": rating,
            "reviewCount": count,
            "distribution": distribution,
            "reviews": reviews,
        }

    def eligibility(self, payment_store: Any, user_id: str, product_id: str) -> dict[str, Any]:
        product_id = self._product_id(product_id)
        order = self._qualifying_order(payment_store, user_id, product_id)
        with self.connect() as db:
            existing = db.execute(
                """SELECT r.*,u.name AS user_name FROM product_reviews r
                   JOIN users u ON u.id=r.user_id
                   WHERE r.user_id=? AND r.product_id=?""",
                (user_id, product_id),
            ).fetchone()
        return {
            "eligible": order is not None,
            "orderId": order.get("id") if order else None,
            "existingReview": self._public_row(existing) if existing is not None else None,
            "reason": None if order else "delivered_purchase_required",
        }

    def create(self, payment_store: Any, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        product_id = self._product_id(payload.get("productId"))
        rating = self._rating(payload.get("rating"))
        title = self._title(payload.get("title"))
        comment = self._comment(payload.get("comment"))
        order = self._qualifying_order(payment_store, user_id, product_id)
        if order is None:
            raise SecurityError(
                403,
                "Only customers with a delivered purchase can review this product.",
                "delivered_purchase_required",
            )
        review_id = f"rev_{secrets.token_hex(12)}"
        now = _now()
        try:
            with self.connect() as db:
                db.execute(
                    """INSERT INTO product_reviews(
                       id,product_id,user_id,order_id,rating,title,comment,status,created_at,updated_at
                       ) VALUES(?,?,?,?,?,?,?,'published',?,?)""",
                    (review_id, product_id, user_id, order["id"], rating, title, comment, now, now),
                )
                db.commit()
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint failed" in str(exc):
                raise SecurityError(409, "You have already reviewed this product.", "review_exists") from exc
            raise
        return self.get_owned(review_id, user_id)

    def get_owned(self, review_id: str, user_id: str) -> dict[str, Any]:
        return self._public_row(self._owned_row(review_id, user_id))

    def edit(self, user_id: str, review_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._owned_row(review_id, user_id)
        rating = self._rating(payload.get("rating"))
        title = self._title(payload.get("title"))
        comment = self._comment(payload.get("comment"))
        with self.connect() as db:
            db.execute(
                """UPDATE product_reviews
                   SET rating=?,title=?,comment=?,updated_at=?
                   WHERE id=? AND user_id=?""",
                (rating, title, comment, _now(), review_id, user_id),
            )
            db.commit()
        return self.get_owned(review_id, user_id)

    def delete(self, user_id: str, review_id: str) -> None:
        self._owned_row(review_id, user_id)
        with self.connect() as db:
            db.execute(
                "DELETE FROM product_reviews WHERE id=? AND user_id=?",
                (review_id, user_id),
            )
            db.commit()
