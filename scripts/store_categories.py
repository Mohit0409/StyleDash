"""Canonical store category choices for partner/shop-owner applications.

Store categories intentionally mirror the public product catalogue taxonomy
defined in ``catalog_normalization.PRODUCT_CATEGORIES``. The frontend renders
the same vocabulary from ``src/data/categories.ts`` (``STORE_CATEGORIES``).

Legacy values such as "General Store" are NOT valid store categories; the
server rejects them while older drafts keep their stored value untouched.
"""

STORE_CATEGORIES = frozenset(
    {
        "Clothing & Fashion",
        "Footwear",
        "Accessories",
        "Beauty & Personal Care",
        "Electronics",
        "Gifts",
        "Home & Living",
    }
)
