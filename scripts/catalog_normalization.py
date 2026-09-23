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
    "Clothing & Fashion", "Footwear", "Accessories", "Beauty & Personal Care",
    "Electronics", "Gifts", "Home & Living",
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

SUBCATEGORY_ALIASES = {
    "sneaker": "Sneakers", "sneakers": "Sneakers", "semi sneaker": "Sneakers",
    "sport shoe": "Sports Shoes", "sport shoes": "Sports Shoes",
    "sports shoe": "Sports Shoes", "sports shoes": "Sports Shoes",
    "running shoe": "Running Shoes", "running shoes": "Running Shoes",
    "slider": "Sliders", "sliders": "Sliders", "slides": "Sliders",
    "platform slider": "Sliders", "flipflop slider": "Sliders",
    "slipper": "Slippers & Flip-Flops", "slippers": "Slippers & Flip-Flops",
    "sleeper": "Slippers & Flip-Flops", "sleepers": "Slippers & Flip-Flops",
    "flip flop": "Slippers & Flip-Flops", "flip flops": "Slippers & Flip-Flops",
    "flipflop": "Slippers & Flip-Flops", "flipflops": "Slippers & Flip-Flops",
    "flipflop slipper": "Slippers & Flip-Flops", "chappal slipper": "Slippers & Flip-Flops",
    "loafer": "Loafers", "loafers": "Loafers", "slip on loafer": "Loafers",
    "moc shoe without lace": "Loafers", "crocs": "Clogs & Crocs",
    "watch": "Watches", "watch2": "Watches", "watches": "Watches",
    "accesories": "Accessories", "accessory": "Accessories", "accessories": "Accessories",
    "jewellery": "Fashion Jewellery", "jewelry": "Fashion Jewellery",
    "traditional accessories": "Fashion Jewellery", "hair accessories": "Hair Accessories",
    "skincare": "Skin Care", "skin care": "Skin Care",
    "sanitary pads": "Feminine Care",
    "gift hamper": "Gift Hampers", "gift hampers": "Gift Hampers",
    "home appliance": "Home Appliances", "home appliances": "Home Appliances",
    "rc toys": "Remote Control Toys", "drones rc toys": "Remote Control Toys",
}

CATEGORY_TAG_ALIASES = {
    "Clothing & Fashion": ("clothing", "fashion", "apparel"),
    "Footwear": ("footwear", "shoes"),
    "Accessories": ("accessories", "fashion accessories"),
    "Beauty & Personal Care": ("beauty", "personal care"),
    "Electronics": ("electronics", "gadgets"),
    "Gifts": ("gifts", "gift items"),
    "Home & Living": ("home and living", "home essentials"),
}

DEPARTMENT_TAG_ALIASES = {
    "men": ("men", "mens"),
    "women": ("women", "womens"),
    "kids": ("kids", "children"),
    "unisex": ("unisex",),
}


def infer_product_category(name: str, description: str) -> str | None:
    text = f"{name} {description}".casefold()
    if re.search(r"\b(perfumes?|fragrances?|deodorants?|deos?|face\s*wash|face\s*cream|skin\s*care|skincare|hair\s*care|haircare|grooming|cosmetics?|makeup|beauty|personal\s*care)\b", text):
        return "Beauty & Personal Care"
    if re.search(r"\b(sliders?|sneakers?|shoes?|sandals?|loafers?|footwear)\b", text):
        return "Footwear"
    if re.search(r"\b(earrings?|jhumk(?:a|i)s?|jewell?ery|necklaces?|bracelets?|bangles?|belts?|handbags?|bags?)\b", text):
        return "Accessories"
    if re.search(r"\b(gifts?|gift\s*(?:box|boxes|hamper|hampers|wrap|wrapping)|teddy\s*bear|soft\s*toy|greeting\s*cards?)\b", text):
        return "Gifts"
    if re.search(r"\b(home\s*(?:decor|décor|living)|kitchen(?:ware)?|cookware|bedding|bedsheets?|cushions?|curtains?|storage|organis(?:er|ers|ation)|furniture|household)\b", text):
        return "Home & Living"
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
        "beauty": "Beauty & Personal Care", "beauty personal care": "Beauty & Personal Care",
        "personal care": "Beauty & Personal Care", "perfume": "Beauty & Personal Care",
        "fragrance": "Beauty & Personal Care", "deodorant": "Beauty & Personal Care",
        "cosmetic": "Beauty & Personal Care", "cosmetics": "Beauty & Personal Care",
        "skin care": "Beauty & Personal Care", "skincare": "Beauty & Personal Care",
        "hair care": "Beauty & Personal Care", "haircare": "Beauty & Personal Care",
        "grooming": "Beauty & Personal Care",
        "gift": "Gifts", "gifts": "Gifts", "gift box": "Gifts", "gift boxes": "Gifts",
        "gift hamper": "Gifts", "gift hampers": "Gifts", "greeting cards": "Gifts",
        "home": "Home & Living", "home living": "Home & Living", "home and living": "Home & Living",
        "home decor": "Home & Living", "home décor": "Home & Living", "household": "Home & Living",
        "clothing": "Clothing & Fashion", "fashion": "Clothing & Fashion", "apparel": "Clothing & Fashion",
    }
    normalized = aliases.get(key)
    inferred = infer_product_category(name, description)
    if normalized is None:
        if inferred is None:
            raise SecurityError(400, "Invalid product category.", "invalid_product")
        return inferred
    if normalized == "Clothing & Fashion" and inferred in {"Footwear", "Accessories", "Beauty & Personal Care", "Gifts", "Home & Living"}:
        return inferred
    if normalized == "Accessories" and inferred == "Beauty & Personal Care":
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
        raw = clean_text(value, "subcategory", 1, 100)
        return SUBCATEGORY_ALIASES.get(_key(raw), raw)
    text = name.casefold()
    if category == "Clothing & Fashion":
        if re.search(r"\bt-?shirts?|tees?\b", text): return "T-Shirts"
        if re.search(r"\bshirts?\b", text): return "Shirts"
        if re.search(r"\bjeans?\b", text): return "Jeans"
        if re.search(r"\b(?:trousers?|pants?|chinos?)\b", text): return "Trousers"
        if re.search(r"\b(?:hoodies?|sweatshirts?|jackets?)\b", text): return "Hoodies & Jackets"
        if re.search(r"\b(?:kurtas?|sarees?|ethnic)\b", text): return "Ethnic Wear"
        if re.search(r"\b(?:dresses?|frocks?)\b", text): return "Dresses"
        if re.search(r"\b(?:tops?|blouses?)\b", text): return "Tops"
        if re.search(r"\b(?:shorts?|track pants?|gym)\b", text): return "Activewear"
    if category == "Accessories":
        if re.search(r"\b(earrings?|jhumk(?:a|i)s?)\b", text): return "Earrings"
        if re.search(r"\b(watch(?:es)?|smartwatch(?:es)?)\b", text): return "Watches"
        if re.search(r"\b(necklaces?|bracelets?|bangles?|jewell?ery)\b", text): return "Fashion Jewellery"
        if re.search(r"\b(handbags?|backpacks?|totes?|wallets?|bags?)\b", text): return "Bags & Wallets"
        if re.search(r"\bhair\s+(?:clip|clips|band|bands|accessor(?:y|ies))\b", text): return "Hair Accessories"
        if re.search(r"\b(?:belts?|caps?|sunglasses?|scarves?)\b", text): return "Fashion Accessories"
    if category == "Beauty & Personal Care":
        if re.search(r"\b(perfumes?|fragrances?)\b", text): return "Perfume"
        if re.search(r"\b(deodorants?|deos?)\b", text): return "Deodorant"
        if re.search(r"\bface\s*wash\b", text): return "Face Wash"
        if re.search(r"\bface\s*cream\b", text): return "Face Cream"
        if re.search(r"\b(skin\s*care|skincare)\b", text): return "Skin Care"
        if re.search(r"\b(hair\s*care|haircare)\b", text): return "Hair Care"
        if re.search(r"\bgrooming\b", text): return "Grooming"
        if re.search(r"\b(cosmetics?|makeup)\b", text): return "Cosmetics"
    if category == "Gifts":
        if re.search(r"\b(gift\s*(?:box|boxes)|hampers?)\b", text): return "Gift Hampers"
        if re.search(r"\b(teddy\s*bear|soft\s*toy)\b", text): return "Soft Toys"
        if re.search(r"\b(greeting\s*cards?)\b", text): return "Greeting Cards"
    if category == "Home & Living":
        if re.search(r"\b(kitchen|cookware)\b", text): return "Kitchen & Dining"
        if re.search(r"\b(bedding|bedsheets?|cushions?|curtains?)\b", text): return "Bedding & Furnishings"
        if re.search(r"\b(storage|organis(?:er|ers|ation))\b", text): return "Storage & Organisation"
        if re.search(r"\b(home\s*(?:decor|décor)|furniture)\b", text): return "Home Decor"
    if category == "Footwear":
        if re.search(r"\b(?:flip[ -]?flops?|slippers?|sleepers?|chappals?)\b", text): return "Slippers & Flip-Flops"
        if re.search(r"\b(?:loafers?|moccasins?)\b", text): return "Loafers"
        if re.search(r"\b(?:crocs?|clogs?)\b", text): return "Clogs & Crocs"
        if re.search(r"\bsliders?\b", text): return "Sliders"
        if re.search(r"\bsneakers?\b", text): return "Sneakers"
        if re.search(r"\brunning\b", text): return "Running Shoes"
        if re.search(r"\bsports?\b", text): return "Sports Shoes"
        if re.search(r"\bsandals?\b", text): return "Sandals"
        if re.search(r"\bshoes?\b", text): return "Shoes"
    if category == "Electronics":
        if re.search(r"\b(?:earbuds?|headphones?|earphones?|speakers?)\b", text): return "Audio"
        if re.search(r"\b(?:chargers?|cables?|power banks?)\b", text): return "Mobile Accessories"
        if re.search(r"\b(?:smartwatches?|smart watches?)\b", text): return "Wearables"
        if re.search(r"\b(?:rc|remote control|drones?)\b", text): return "Remote Control Toys"
    return None


def build_product_tags(
    *,
    name: str,
    brand: str | None,
    store_name: str,
    department: str,
    category: str,
    subcategory: str | None,
) -> list[str]:
    """Build bounded public discovery tags from already-public catalogue fields."""
    candidates: list[str | None] = [
        "local-shop", name, brand, store_name, department, category, subcategory,
        *DEPARTMENT_TAG_ALIASES.get(department, ()),
        *CATEGORY_TAG_ALIASES.get(category, ()),
    ]
    if subcategory:
        subcategory_key = _key(subcategory)
        candidates.extend(
            alias for alias, canonical in SUBCATEGORY_ALIASES.items()
            if _key(canonical) == subcategory_key
        )

    tags: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate:
            continue
        tag = re.sub(r"\s+", " ", str(candidate)).strip().casefold()
        if not tag or len(tag) > 100 or tag in seen:
            continue
        seen.add(tag)
        tags.append(tag)
        if len(tags) == 24:
            break
    return tags


def normalize_delivery_type(value: Any) -> str:
    key = _key(value or "normal")
    normalized = DELIVERY_ALIASES.get(key)
    if normalized is None:
        raise SecurityError(400, "Delivery type must be normal, express or both.", "invalid_product")
    return normalized
