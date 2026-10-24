"""Canonical store category choices for partner/shop-owner applications.

Store categories intentionally mirror the public product catalogue taxonomy
defined in ``catalog_normalization.PRODUCT_CATEGORIES``. The frontend renders
the same vocabulary from ``src/data/categories.ts`` (``STORE_CATEGORIES``).

"General Store" remains valid for older shops; other legacy labels stay
preserved until explicitly reviewed.
"""

STORE_CATEGORIES = frozenset({"Clothing & Fashion", "Footwear", "Accessories", "Beauty & Personal Care", "Electronics", "Gifts", "Groceries", "Home & Living", "Health & Pharmacy", "Health & Nutrition", "Baby Care", "Pet Supplies", "Mobile Accessories", "Automotive Accessories", "Toys & Games", "Stationery & Books", "Sports & Fitness", "Hardware & Tools", "General Store"})
