"""Canonical catalogue metadata normalization for seller products."""
from __future__ import annotations

import re
from typing import Any

try:
    from styledash_security import SecurityError, clean_text
except ModuleNotFoundError:
    from scripts.styledash_security import SecurityError, clean_text

CANONICAL_DEPARTMENTS = {"men", "women", "kids", "unisex"}
LEGACY_DEPARTMENT_CLASSES = {"footwear", "accessories"}
PRODUCT_CATEGORIES = {
    "Clothing & Fashion", "Footwear", "Accessories",
    "Electronics", "Home & Living", "General Store",
}


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


DEPARTMENT_ALIASES = {
    "men": "men", "mens": "men", "male": "men", "man": "men", "gents": "men",
    "women": "women", "womens": "women", "female": "women", "woman": "women",
    "ladies": "women", "lady": "women",
    "kids": "kids", "kid": "kids", "children": "kids", "child": "kids",
    "boys": "kids", "boy": "kids", "girls": "kids", "girl": "kids",
    "unisex": "unisex", "all": "unisex",
}
BRAND_ALIASES = {
    "puma": "Puma", "skechers": "Skechers", "campus": "Campus", "sparx": "Sparx",
}
DELIVERY_ALIASES = {
    "normal": "normal", "standard": "normal", "within a day": "normal", "within day": "normal",
    "express": "express", "weekend express": "express",
    "both": "both", "normal express": "both", "standard express": "both",
}


def infer_product_category(name: str, description: str) -> str | None:
    text = f"{name} {description}".casefold()
    if re.search(r"\b(sliders?|sneakers?|shoes?|sandals?|loafers?|footwear)\b", text):
        return "Footwear"
    if re.search(r"\b(earrings?|jhumk(?:a|i)s?|jewell?ery|necklaces?|bracelets?|bangles?|belts?|handbags?|bags?)\b", text):
        return "Accessories"
    if re.search(r"\b(kurtas?|shirts?|t-?shirts?|tees?|jeans?|trousers?|dresses?|tops?|apparel|clothing)\b", text):
        return "Clothing & Fashion"
    return None
def normalize_product_category(value: Any, *, name: str, description: str, legacy_department: Any = None) -> str:
    legacy = _key(legacy_department)
    if legacy == "footwear":
        return "Footwear"
    if legacy in {"accessory", "accessories"}:
        return "Accessories"
    raw = clean_text(value, "product category", 2, 100)
    key = _key(raw)
    aliases = {
        **{_key(item): item for item in PRODUCT_CATEGORIES},
        "shoe": "Footwear", "shoes": "Footwear", "sneaker": "Footwear",
        "sneakers": "Footwear", "slider": "Footwear", "sliders": "Footwear",
        "accessory": "Accessories", "jewellery": "Accessories", "jewelry": "Accessories",
        "earring": "Accessories", "earrings": "Accessories",
        "clothing": "Clothing & Fashion", "fashion": "Clothing & Fashion", "apparel": "Clothing & Fashion",
    }
    normalized = aliases.get(key)
    inferred = infer_product_category(name, description)
    if normalized is None:
        if inferred is None:
            raise SecurityError(400, "Invalid product category.", "invalid_product")
        return inferred
    if normalized == "Clothing & Fashion" and inferred in {"Footwear", "Accessories"}:
        return inferred
    return normalized
def infer_audience(name: str, description: str, category: str) -> str | None:
    text = f"{name} {description}".casefold()
    if re.search(r"\bunisex\b", text):
        return "unisex"
    found: set[str] = set()
    if re.search(r"\b(women|woman|womens|ladies|lady|female)\b", text):
        found.add("women")
    if re.search(r"\b(men|man|mens|gents|male)\b", text):
        found.add("men")
    if re.search(r"\b(kids?|children|child|boys?|girls?)\b", text):
        found.add("kids")
    if len(found) == 1:
        return next(iter(found))
    if not found and category == "Accessories" and re.search(r"\b(earrings?|jhumk(?:a|i)s?)\b", text):
        return "women"
    return None


def normalize_department(value: Any, *, name: str, description: str, category: str, allow_legacy: bool = False) -> str:
    key = _key(value)
    if key in DEPARTMENT_ALIASES:
        return DEPARTMENT_ALIASES[key]
    inferred = infer_audience(name, description, category)
    if key in LEGACY_DEPARTMENT_CLASSES:
        if inferred:
            return inferred
        if allow_legacy:
            return key
        raise SecurityError(400, "Department must be men, women, kids or unisex; use Category for footwear/accessories.", "invalid_product")
    if not key and inferred:
        return inferred
    raise SecurityError(400, "Invalid product department.", "invalid_product")


def normalize_brand(value: Any, *, name: str) -> str | None:
    if value is None or value == "":
        name_key = _key(name)
        for key, canonical in BRAND_ALIASES.items():
            if name_key == key or name_key.startswith(key + " "):
                return canonical
        return None
    brand = clean_text(value, "brand", 1, 100)
    return BRAND_ALIASES.get(_key(brand), re.sub(r"\s+", " ", brand).strip())


def _number_label(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value).rstrip("0").rstrip(".")


def normalize_size_label(value: Any, category: str) -> str:
    raw = re.sub(r"\s+", " ", clean_text(value, "size", 1, 40)).strip()
    key = re.sub(r"[\s_-]+", " ", raw.casefold()).strip()
    alpha = {
        "xs": "XS", "s": "S", "m": "M", "l": "L", "xl": "XL", "xxl": "XXL", "xxxl": "XXXL",
        "one size": "One Size", "onesize": "One Size", "free size": "One Size", "freesize": "One Size",
    }
    if key in alpha:
        return alpha[key]
    compact = re.sub(r"\s+", "", raw.casefold().replace("-", ""))
    match = re.fullmatch(r"(uk|eu|us)(\d{1,2}(?:\.5)?)", compact)
    if match:
        return f"{match.group(1).upper()} {_number_label(float(match.group(2)))}"
    match = re.fullmatch(r"(\d{1,2}(?:\.5)?)(uk|eu|us)", compact)
    if match:
        return f"{match.group(2).upper()} {_number_label(float(match.group(1)))}"
    if category == "Footwear" and re.fullmatch(r"\d{1,2}(?:\.5)?", compact):
        number = float(compact)
        if 3 <= number <= 14:
            return f"UK {_number_label(number)}"
        if number.is_integer() and 35 <= number <= 50:
            return f"EU {int(number)}"
    return raw


def normalize_subcategory(value: Any, *, name: str, category: str) -> str | None:
    if value not in {None, ""}:
        return clean_text(value, "subcategory", 1, 100)
    text = name.casefold()
    if category == "Accessories" and re.search(r"\b(earrings?|jhumk(?:a|i)s?)\b", text):
        return "Earrings"
    if category == "Footwear":
        if re.search(r"\bsliders?\b", text): return "Sliders"
        if re.search(r"\bsneakers?\b", text): return "Sneakers"
        if re.search(r"\brunning\b", text): return "Running Shoes"
        if re.search(r"\bsports?\b", text): return "Sports Shoes"
        if re.search(r"\bsandals?\b", text): return "Sandals"
        if re.search(r"\bshoes?\b", text): return "Shoes"
    return None
def normalize_delivery_type(value: Any) -> str:
    key = _key(value or "normal")
    normalized = DELIVERY_ALIASES.get(key)
    if normalized is None:
        raise SecurityError(400, "Delivery type must be normal, express or both.", "invalid_product")
    return normalized
