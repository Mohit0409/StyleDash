#!/usr/bin/env python3
"""Serve Vibe4You and provide its same-origin payment API."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import hmac
import io
import ipaddress
import json
import math
import os
import posixpath
import re
import secrets
import struct
import threading
import time
import zlib
from http.cookies import SimpleCookie
from collections import OrderedDict, defaultdict, deque
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, quote, unquote, urlsplit
from xml.sax.saxutils import escape as xml_escape

try:
    import fcntl
except ImportError:  # Windows test environment; Termux provides fcntl.
    fcntl = None

try:
    from styledash_security import COOKIE_NAME, SecurityError, SecurityStore, normalize_email, token_hash
except ModuleNotFoundError:  # Repository test import path.
    from scripts.styledash_security import COOKIE_NAME, SecurityError, SecurityStore, normalize_email, token_hash

try:
    from styledash_shops import ShopWorkflow
except ModuleNotFoundError:  # Repository test import path.
    from scripts.styledash_shops import ShopWorkflow

try:
    from scripts.styledash_delivery_zone import DeliveryZoneConfigError, DeliveryZoneIndex
    from scripts.styledash_delivery_zone_store import DeliveryZoneStore
except ModuleNotFoundError:  # Standalone deployed import path.
    from styledash_delivery_zone import DeliveryZoneConfigError, DeliveryZoneIndex
    from styledash_delivery_zone_store import DeliveryZoneStore

try:
    from styledash_reviews import ReviewWorkflow
except ModuleNotFoundError:  # Repository test import path.
    from scripts.styledash_reviews import ReviewWorkflow

try:
    from styledash_mail import PasswordResetDeliveryQueue, SmtpPasswordResetSender
except ModuleNotFoundError:  # Repository test import path.
    from scripts.styledash_mail import PasswordResetDeliveryQueue, SmtpPasswordResetSender

try:
    from styledash_registration_email import PendingEmailRegistration, SmtpRegistrationSender
except ModuleNotFoundError:  # Repository test import path.
    from scripts.styledash_registration_email import PendingEmailRegistration, SmtpRegistrationSender

try:
    from styledash_notify import mask_email, mask_phone, owner_notifier
except ModuleNotFoundError:  # Repository test import path.
    from scripts.styledash_notify import mask_email, mask_phone, owner_notifier

try:
    from receipt_pdf import build_receipt_pdf
except ModuleNotFoundError:
    from scripts.receipt_pdf import build_receipt_pdf

try:
    from gst_phase1_registry import (
        OWNER_APPROVAL_DATE as GST_PHASE1_OWNER_APPROVAL_DATE,
        POLICY_ID as GST_PHASE1_POLICY_ID,
        GstPhase1ClassificationError,
        classification_for_product,
    )
except ModuleNotFoundError:
    from scripts.gst_phase1_registry import (
        OWNER_APPROVAL_DATE as GST_PHASE1_OWNER_APPROVAL_DATE,
        POLICY_ID as GST_PHASE1_POLICY_ID,
        GstPhase1ClassificationError,
        classification_for_product,
    )
try:
    from invoice_admin_gateway import InvoiceGateway, InvoiceDraftError
    from tax_classification_registry import TaxClassificationRegistry
except ModuleNotFoundError:
    from scripts.invoice_admin_gateway import InvoiceGateway, InvoiceDraftError
    from scripts.tax_classification_registry import TaxClassificationRegistry

try:
    import razorpay
except ImportError:  # The static site and COD can still start without the SDK.
    razorpay = None


MAX_BODY_BYTES = 64 * 1024
PRODUCT_IMAGE_MAX_BYTES = 500 * 1024
PRODUCT_IMAGE_REQUEST_MAX_BYTES = 700 * 1024
PRODUCT_IMAGE_ROUTE_PATTERN = re.compile(r"^/media/product-images/([0-9a-f]{32}\.(?:webp|jpg|png))$")
API_PREFIX = "/api/"
TRY_AT_HOME_FEE_RUPEES = 50
TRY_AT_HOME_LATE_FEE_RUPEES = 50
TRY_AT_HOME_MINUTES = 15
EXCHANGE_FEE_RUPEES = 50
EXCHANGE_WINDOW_DAYS = 2
CANCELLATION_AFTER_DISPATCH_FEE_RUPEES = 50

NEEMUCH_LOCAL_PAGES = {
    "/neemuch/shoes": {
        "title": "Buy Shoes in Neemuch | Sneakers, Sports Shoes & Footwear | Vibe4You",
        "description": "Shop shoes in Neemuch from local stores on Vibe4You. Browse sneakers, sports shoes, sliders, sandals and more with Same Day Delivery in the supported Neemuch area.",
        "heading": "Buy Shoes in Neemuch",
        "intro": "Looking for good shoes in Neemuch? Compare footwear from local Neemuch stores in one place, including sneakers, sports shoes, sliders, sandals, loafers and everyday footwear.",
        "category": "Footwear",
        "catalogue": "/products?category=Footwear",
    },
    "/neemuch/clothes": {
        "title": "Shop Clothes in Neemuch | Men, Women & Kids Fashion | Vibe4You",
        "description": "Buy clothes in Neemuch online from local shops. Discover T-shirts, shirts, jeans, tops, kurtas and more with Same Day Delivery across the supported Neemuch service area.",
        "heading": "Shop Clothes in Neemuch",
        "intro": "Find clothes from local Neemuch shops without visiting multiple stores. Browse men's, women's and kids fashion, compare styles and prices, and order locally through Vibe4You.",
        "category": "Clothing & Fashion",
        "catalogue": "/products?category=Clothing%20%26%20Fashion",
    },
    "/neemuch/mens-clothing": {
        "title": "Men's Clothing in Neemuch | T-Shirts, Shirts & Jeans | Vibe4You",
        "description": "Shop men's clothing in Neemuch from local stores. Browse T-shirts, shirts, jeans and more with convenient local ordering and Same Day Delivery in supported areas.",
        "heading": "Men's Clothing in Neemuch",
        "intro": "Browse men's fashion available from local Neemuch sellers, including T-shirts, shirts, jeans and everyday styles. Vibe4You brings local store inventory together in one searchable catalogue.",
        "category": "Clothing & Fashion",
        "department": "men",
        "catalogue": "/products?dept=men&category=Clothing%20%26%20Fashion",
    },
    "/neemuch/womens-clothing": {
        "title": "Women's Clothing in Neemuch | Tops, Jeans, Kurtas & More | Vibe4You",
        "description": "Shop women's clothing in Neemuch from local boutiques and stores. Browse tops, jeans, kurtas, sets and more with Same Day Delivery in supported Neemuch areas.",
        "heading": "Women's Clothing in Neemuch",
        "intro": "Discover women's fashion from local Neemuch stores, including tops, jeans, kurtas, co-ords and occasion wear. Compare local choices online before you order.",
        "category": "Clothing & Fashion",
        "department": "women",
        "catalogue": "/products?dept=women&category=Clothing%20%26%20Fashion",
    },
    "/neemuch/kids-wear": {
        "title": "Kids Wear in Neemuch | Boys & Girls Clothing | Vibe4You",
        "description": "Shop kids wear in Neemuch from local sellers. Browse clothing for boys and girls with local ordering and Same Day Delivery in supported areas.",
        "heading": "Kids Wear in Neemuch",
        "intro": "Find kids clothing from Neemuch stores in one catalogue. Browse current local options for boys and girls and order from nearby sellers through Vibe4You.",
        "category": "Clothing & Fashion",
        "department": "kids",
        "catalogue": "/products?dept=kids&category=Clothing%20%26%20Fashion",
    },
    "/neemuch/watches": {
        "title": "Buy Watches in Neemuch | Men & Women Watches | Vibe4You",
        "description": "Shop watches in Neemuch from local stores on Vibe4You. Browse analog, fashion and everyday watches with local availability and Same Day Delivery in supported areas.",
        "heading": "Buy Watches in Neemuch",
        "intro": "Looking for watches in Neemuch? Browse watches stocked by local stores, compare styles and prices, and order from nearby sellers through Vibe4You.",
        "category": "Accessories",
        "subcategories": ("Watches",),
        "terms": ("watch",),
        "catalogue": "/products?category=Accessories&subcategory=Watches",
    },
    "/neemuch/jewellery": {
        "title": "Jewellery in Neemuch | Earrings, Bangles & Necklaces | Vibe4You",
        "description": "Shop fashion jewellery in Neemuch from local sellers. Browse earrings, bangles, necklaces, bracelets and more on Vibe4You.",
        "heading": "Fashion Jewellery in Neemuch",
        "intro": "Explore fashion jewellery sold by local Neemuch shops, including earrings, bangles, necklaces and bracelets. Browse styles online and buy locally through Vibe4You.",
        "category": "Accessories",
        "subcategories": ("Fashion Jewellery", "Earrings", "Bangles", "Necklaces", "Bracelets"),
        "terms": ("earring", "bangle", "necklace", "bracelet", "jewellery", "jewelry", "jhumki"),
        "catalogue": "/products?category=Accessories",
    },
    "/neemuch/beauty": {
        "title": "Beauty & Personal Care in Neemuch | Shop Local Online | Vibe4You",
        "description": "Buy beauty and personal care products in Neemuch from local stores. Browse hair care, skin care, perfumes, baby care and more on Vibe4You.",
        "heading": "Beauty & Personal Care in Neemuch",
        "intro": "Shop beauty and personal care products available from local Neemuch sellers, including hair care, skin care, perfumes, baby care and daily essentials.",
        "category": "Beauty & Personal Care",
        "catalogue": "/products?category=Beauty%20%26%20Personal%20Care",
    },
    "/neemuch/gifts": {
        "title": "Buy Gifts in Neemuch | Local Gift Shopping & Delivery | Vibe4You",
        "description": "Find gifts in Neemuch from local sellers on Vibe4You. Browse gift options online and order locally with Same Day Delivery in the supported Neemuch area.",
        "heading": "Buy Gifts in Neemuch",
        "intro": "Need a gift in Neemuch? Browse gift options from local sellers, compare available products and order without searching store by store.",
        "category": "Gifts",
        "catalogue": "/products?category=Gifts",
    },
    "/neemuch/same-day-delivery": {
        "title": "Same Day Delivery in Neemuch | Shop Local Products Online | Vibe4You",
        "description": "Shop products from local Neemuch stores with Same Day Delivery across the supported service area. Browse fashion, footwear, beauty, accessories, gifts and more.",
        "heading": "Same Day Shopping & Delivery in Neemuch",
        "intro": "Vibe4You brings products from local Neemuch stores into one online catalogue. Browse what is available nearby and get eligible local orders delivered the same day in the supported service area.",
        "all_products": True,
        "catalogue": "/products",
    },
    "/neemuch/shops": {
        "title": "Local Shops in Neemuch | Shop Online from Neemuch Stores | Vibe4You",
        "description": "Find local shops in Neemuch on Vibe4You. Browse every participating Neemuch store, see what each sells and order online with Same Day Delivery in supported areas.",
        "heading": "Local Shops in Neemuch",
        "intro": "Looking for shops in Neemuch? Vibe4You brings local Neemuch stores online in one place. Open any shop to see its products, compare prices and order with Same Day Delivery in supported areas.",
        "directory": "stores",
        "catalogue": "/stores",
    },
    "/neemuch/casio-watches": {
        "title": "Casio Watches in Neemuch | Buy Casio Watch Online | Vibe4You",
        "description": "Browse Casio watches on Vibe4You with prices, photos and availability. Same Day Delivery in supported Neemuch areas; outside Neemuch, request a prepaid delivery quote.",
        "heading": "Casio Watches in Neemuch",
        "intro": "Looking for a Casio watch in Neemuch? Browse Casio digital, analog and everyday models, compare prices and photos, and order with Same Day Delivery in supported Neemuch areas. Outside Neemuch, request a prepaid delivery quote before ordering.",
        "terms": ("casio",),
        "catalogue": "/products?category=Accessories&subcategory=Watches",
    },
    "/neemuch/lavie-bags": {
        "title": "Lavie Bags in Neemuch | Handbags, Slings & Wallets | Vibe4You",
        "description": "Shop Lavie handbags, sling bags and wallets on Vibe4You. See current prices, colours and photos. Same Day Delivery in supported Neemuch areas; prepaid delivery quote outside Neemuch.",
        "heading": "Lavie Bags in Neemuch",
        "intro": "Looking for a Lavie bag in Neemuch? Browse Lavie handbags, sling bags and wallets, compare colours and prices, and order with Same Day Delivery in supported Neemuch areas. Outside Neemuch, request a prepaid delivery quote before ordering.",
        "terms": ("lavie",),
        "catalogue": "/products?category=Accessories&subcategory=Handbags",
    },
    "/neemuch/handbags": {
        "title": "Handbags & Ladies Bags in Neemuch | Buy Bags Online | Vibe4You",
        "description": "Shop handbags, sling bags and ladies bags in Neemuch from local sellers on Vibe4You. Compare styles and prices with Same Day Delivery in supported areas.",
        "heading": "Handbags & Ladies Bags in Neemuch",
        "intro": "Find handbags, sling bags and everyday ladies bags from Neemuch sellers. Browse current styles and prices in one place and order locally through Vibe4You.",
        "category": "Accessories",
        "subcategories": ("Handbags",),
        "terms": ("handbag", "sling bag"),
        "catalogue": "/products?category=Accessories&subcategory=Handbags",
    },
    "/neemuch/electronics": {
        "title": "Electronics in Neemuch | Mobiles, Covers & Accessories | Vibe4You",
        "description": "Shop electronics in Neemuch from local stores on Vibe4You. Browse mobile phones, covers, chargers, audio and accessories with Same Day Delivery in supported areas.",
        "heading": "Electronics in Neemuch",
        "intro": "Browse electronics from local Neemuch stores, including mobile phones, phone covers, chargers, audio and everyday accessories. Compare options online and order locally through Vibe4You.",
        "category": "Electronics",
        "catalogue": "/products?category=Electronics",
    },
    "/neemuch/mobile-phones": {
        "title": "Mobile Phones in Neemuch | Buy Smartphones Online | Vibe4You",
        "description": "Buy mobile phones in Neemuch from local stores on Vibe4You. Compare smartphones and prices online with Same Day Delivery in supported areas.",
        "heading": "Mobile Phones in Neemuch",
        "intro": "Looking for a mobile phone in Neemuch? Compare smartphones listed by local Neemuch stores, check current prices and order through Vibe4You.",
        "category": "Electronics",
        "subcategories": ("Mobile Phones",),
        "catalogue": "/products?category=Electronics&subcategory=Mobile%20Phones",
    },
    "/neemuch/mobile-covers": {
        "title": "Mobile Covers in Neemuch | Phone Cases Online | Vibe4You",
        "description": "Shop mobile covers and phone cases in Neemuch from local sellers on Vibe4You. Browse designs and prices with Same Day Delivery in supported areas.",
        "heading": "Mobile Covers in Neemuch",
        "intro": "Find phone covers and cases from Neemuch sellers. Browse current designs, compare prices and order locally through Vibe4You.",
        "category": "Electronics",
        "subcategories": ("Mobile Covers",),
        "catalogue": "/products?category=Electronics&subcategory=Mobile%20Covers",
    },
    "/neemuch/mobile-accessories": {
        "title": "Mobile Accessories in Neemuch | Chargers, Cables & More | Vibe4You",
        "description": "Buy mobile accessories in Neemuch from local stores on Vibe4You. Browse chargers, cables, earphones and more with Same Day Delivery in supported areas.",
        "heading": "Mobile Accessories in Neemuch",
        "intro": "Shop mobile accessories sold by Neemuch stores, including chargers, cables and everyday add-ons. Compare options and order locally through Vibe4You.",
        "category": "Electronics",
        "subcategories": ("Mobile Accessories",),
        "catalogue": "/products?category=Electronics&subcategory=Mobile%20Accessories",
    },
    "/neemuch/groceries": {
        "title": "Groceries in Neemuch | Buy Grocery Items Online | Vibe4You",
        "description": "Shop groceries in Neemuch from local stores on Vibe4You. Browse tea, coffee, rice, spices, oils and daily essentials with Same Day Delivery in supported areas.",
        "heading": "Groceries in Neemuch",
        "intro": "Order groceries from local Neemuch stores, including tea and coffee, rice and grains, spices, oils and daily essentials. Compare items online and get Same Day Delivery in supported areas.",
        "category": "Groceries",
        "catalogue": "/products?category=Groceries",
    },
    "/neemuch/home-and-living": {
        "title": "Home & Kitchen Products in Neemuch | Shop Online | Vibe4You",
        "description": "Shop home and kitchen products in Neemuch from local stores on Vibe4You. Browse kitchen appliances and home essentials with Same Day Delivery in supported areas.",
        "heading": "Home & Kitchen Products in Neemuch",
        "intro": "Find home and kitchen products from local Neemuch stores, including kitchen appliances and household essentials. Compare options online and order locally through Vibe4You.",
        "category": "Home & Living",
        "catalogue": "/products?category=Home%20%26%20Living",
    },
}


NEEMUCH_LOCAL_PAGES.update({
    "/neemuch/sneakers": {
        "title": "Sneakers in Neemuch | Casual & Sports Sneakers | Vibe4You",
        "description": "Shop sneakers in Neemuch from local stores. Browse casual, sports and everyday sneakers with current prices and Same Day Delivery in supported areas.",
        "heading": "Sneakers in Neemuch",
        "intro": "Browse sneakers and trainers available from Neemuch footwear sellers, including casual sneakers, sports sneakers and everyday lace-up styles.",
        "category": "Footwear",
        "subcategories": ("Sneakers", "Sports Sneakers"),
        "terms": ("sneaker", "trainer"),
        "catalogue": "/products?category=Footwear&subcategory=Sneakers",
    },
    "/neemuch/sports-shoes": {
        "title": "Sports Shoes in Neemuch | Running Shoes | Vibe4You",
        "description": "Shop sports and running shoes in Neemuch from local footwear stores. Compare current styles and prices with Same Day Delivery in supported areas.",
        "heading": "Sports & Running Shoes in Neemuch",
        "intro": "Find sports shoes, running shoes, training shoes and athletic footwear from participating Neemuch sellers in one local catalogue.",
        "category": "Footwear",
        "subcategories": ("Sports Shoes", "Running Shoes", "Sports & Running Shoes", "Sports Sneakers", "Sport Shoes/Casual Shoes", "Sport Shoes, Casual Shoes", "Sport/Casual Shoes", "Sport Shoes/Running Shoes", "Sport Shoes, Running Shoes"),
        "terms": ("sports shoe", "sport shoe", "running shoe", "training shoe", "athletic shoe"),
        "catalogue": "/products?category=Footwear",
    },
    "/neemuch/slippers": {
        "title": "Slippers & Flip-Flops in Neemuch | Vibe4You",
        "description": "Shop slippers, flip-flops and everyday chappals in Neemuch from local footwear stores with current prices and local delivery options.",
        "heading": "Slippers & Flip-Flops in Neemuch",
        "intro": "Browse slippers, flip-flops and everyday chappals from participating Neemuch footwear sellers and compare currently available styles.",
        "category": "Footwear",
        "subcategories": ("Slippers & Flip-Flops", "Slipper/FlipFlop"),
        "terms": ("slipper", "flip flop", "flip-flop", "chappal"),
        "catalogue": "/products?category=Footwear",
    },
    "/neemuch/sliders": {
        "title": "Sliders & Slides in Neemuch | Shop Footwear | Vibe4You",
        "description": "Shop sliders and slides in Neemuch from local footwear stores. Browse comfort, platform and everyday styles with local delivery options.",
        "heading": "Sliders & Slides in Neemuch",
        "intro": "Find sliders, slides and comfortable slip-on footwear from Neemuch sellers, including everyday, comfort and platform styles.",
        "category": "Footwear",
        "subcategories": ("Sliders", "Comfort Slides", "Platform Slides"),
        "terms": ("slider", "slide", "slip on"),
        "catalogue": "/products?category=Footwear&subcategory=Sliders",
    },
    "/neemuch/womens-footwear": {
        "title": "Women's Footwear in Neemuch | Flats, Heels & Sandals | Vibe4You",
        "description": "Shop women's and ladies footwear in Neemuch. Browse flats, heels, sandals, slippers and shoes from local sellers on Vibe4You.",
        "heading": "Women's Footwear in Neemuch",
        "intro": "Browse women's and ladies footwear from Neemuch stores, including flats, heels, sandals, slippers, sneakers and everyday shoes.",
        "category": "Footwear",
        "department": "women",
        "catalogue": "/products?dept=women&category=Footwear",
    },
    "/neemuch/t-shirts": {
        "title": "T-Shirts & Tees in Neemuch | Men's & Women's Styles | Vibe4You",
        "description": "Shop T-shirts and tees in Neemuch from local clothing stores. Browse casual, polo and everyday styles for men and women.",
        "heading": "T-Shirts & Tees in Neemuch",
        "intro": "Find T-shirts, tees and polo T-shirts from Neemuch fashion sellers, including casual and everyday styles for men and women.",
        "category": "Clothing & Fashion",
        "subcategories": ("T-Shirts", "T-Shirt", "Polo T-Shirt"),
        "terms": ("t-shirt", "t shirt", "tee"),
        "catalogue": "/products?category=Clothing%20%26%20Fashion",
    },
    "/neemuch/shirts": {
        "title": "Shirts in Neemuch | Casual & Formal Shirts | Vibe4You",
        "description": "Shop shirts in Neemuch from local clothing stores. Browse casual, formal and everyday shirts with current local availability.",
        "heading": "Shirts in Neemuch",
        "intro": "Browse casual shirts, formal shirts and everyday button-down styles available from participating Neemuch clothing sellers.",
        "category": "Clothing & Fashion",
        "subcategories": ("Shirts",),
        "catalogue": "/products?category=Clothing%20%26%20Fashion&subcategory=Shirts",
    },
    "/neemuch/jeans": {
        "title": "Jeans in Neemuch | Men's & Women's Denim | Vibe4You",
        "description": "Shop jeans and denim in Neemuch from local clothing stores. Compare men's and women's styles and current prices on Vibe4You.",
        "heading": "Jeans & Denim in Neemuch",
        "intro": "Find jeans and denim styles for men and women from Neemuch fashion sellers and compare current local listings in one place.",
        "category": "Clothing & Fashion",
        "subcategories": ("Jeans",),
        "terms": ("jeans", "denim"),
        "catalogue": "/products?category=Clothing%20%26%20Fashion&subcategory=Jeans",
    },
    "/neemuch/earrings": {
        "title": "Earrings in Neemuch | Jhumka & Fashion Earrings | Vibe4You",
        "description": "Shop earrings and jhumkas in Neemuch from local fashion jewellery sellers. Browse current styles and prices on Vibe4You.",
        "heading": "Earrings & Jhumkas in Neemuch",
        "intro": "Browse earrings, jhumkas, jhumkis and other fashion earring styles available from participating Neemuch jewellery sellers.",
        "category": "Accessories",
        "subcategories": ("Earrings",),
        "terms": ("earring", "jhumka", "jhumki"),
        "catalogue": "/products?category=Accessories&subcategory=Earrings",
    },
    "/neemuch/shampoos": {
        "title": "Shampoo in Neemuch | Hair Shampoo & Conditioner | Vibe4You",
        "description": "Shop shampoo, hair shampoo and conditioner in Neemuch from local beauty stores. Compare current brands, sizes and prices.",
        "heading": "Shampoo & Hair Care in Neemuch",
        "intro": "Browse shampoos, hair cleansers and shampoo-and-conditioner products available from participating Neemuch beauty sellers.",
        "category": "Beauty & Personal Care",
        "subcategories": ("Hair Shampoos", "Shampoo", "Shampoo & Conditioner"),
        "terms": ("shampoo", "hair cleanser"),
        "catalogue": "/products?category=Beauty%20%26%20Personal%20Care",
    },
    "/neemuch/soaps": {
        "title": "Soap & Body Wash in Neemuch | Bath & Body Care | Vibe4You",
        "description": "Shop bath soap, soap bars and body wash in Neemuch from local personal care stores. Compare current brands, sizes and prices.",
        "heading": "Soap & Body Wash in Neemuch",
        "intro": "Find bath soaps, soap bars, body wash and everyday bath products from participating Neemuch personal care sellers.",
        "category": "Beauty & Personal Care",
        "subcategories": ("Bath Soaps & Bars", "Bath Soaps", "Soaps & Body washes", "Body Wash", "Baby Bath & Body"),
        "terms": ("soap", "body wash", "bath bar"),
        "catalogue": "/products?category=Beauty%20%26%20Personal%20Care",
    },
    "/neemuch/baby-care": {
        "title": "Baby Care in Neemuch | Diapers, Skin & Hair Care | Vibe4You",
        "description": "Shop baby care products in Neemuch, including diapers, wipes, baby skin care, hair care and bath products from local stores.",
        "heading": "Baby Care Products in Neemuch",
        "intro": "Browse baby care essentials from Neemuch sellers, including diapers and wipes, baby skin care, baby hair care and bath products.",
        "category": "Beauty & Personal Care",
        "subcategories": ("Baby Care", "Diapers & Wipes", "Baby Skin Care", "Baby Hair Care", "Baby Bath & Body", "Baby Diapers"),
        "terms": ("baby care", "baby diaper", "baby wipes", "baby shampoo"),
        "catalogue": "/products?category=Beauty%20%26%20Personal%20Care",
    },
    "/neemuch/skin-care": {
        "title": "Skin Care in Neemuch | Face Wash, Creams & Serums | Vibe4You",
        "description": "Shop skin care in Neemuch from local beauty stores. Browse face wash, creams, moisturizers, serums, sunscreens and more.",
        "heading": "Skin Care in Neemuch",
        "intro": "Explore skin care and skincare products from Neemuch sellers, including face wash, cleansers, creams, moisturizers, serums and sunscreens.",
        "category": "Beauty & Personal Care",
        "subcategories": ("Skin Care", "Face Wash", "Face Cleansers", "Face washes, Packs & Scrubs", "Face Moisturizers", "Face Serums", "Sunscreens", "Moisturizers & Lotions", "Creams & Moisturizers"),
        "terms": ("skin care", "skincare", "face wash", "moisturizer", "serum", "sunscreen"),
        "catalogue": "/products?category=Beauty%20%26%20Personal%20Care",
    },
    "/neemuch/perfumes": {
        "title": "Perfume in Neemuch | Fragrance, Body Spray & Deo | Vibe4You",
        "description": "Shop perfume, fragrance, body spray and deodorant in Neemuch from local beauty and personal care sellers.",
        "heading": "Perfume & Fragrance in Neemuch",
        "intro": "Browse perfumes, fragrances, body sprays and deodorants currently available from participating Neemuch personal care stores.",
        "category": "Beauty & Personal Care",
        "subcategories": ("Perfume", "Body Spray", "Deodorant"),
        "terms": ("perfume", "fragrance", "body spray", "deodorant", "deo"),
        "catalogue": "/products?category=Beauty%20%26%20Personal%20Care",
    },
    "/neemuch/tea-and-coffee": {
        "title": "Tea & Coffee in Neemuch | Grocery Shopping | Vibe4You",
        "description": "Shop tea and coffee in Neemuch from local grocery stores. Compare current brands, pack sizes and prices on Vibe4You.",
        "heading": "Tea & Coffee in Neemuch",
        "intro": "Browse tea, chai, coffee and everyday hot-beverage products available from participating Neemuch grocery sellers.",
        "category": "Groceries",
        "subcategories": ("Tea & Coffee",),
        "terms": ("tea", "chai", "coffee"),
        "catalogue": "/products?category=Groceries&subcategory=Tea%20%26%20Coffee",
    },
    "/neemuch/spices": {
        "title": "Spices, Masala, Sugar & Salt in Neemuch | Vibe4You",
        "description": "Shop spices, masala, sugar and salt in Neemuch from local grocery stores. Compare current packs and prices on Vibe4You.",
        "heading": "Spices, Masala, Sugar & Salt in Neemuch",
        "intro": "Find spices, masala, sugar, salt and related cooking staples from participating Neemuch grocery sellers.",
        "category": "Groceries",
        "subcategories": ("Sugar, Salt & Spices", "Sugar & Salt", "Spices"),
        "terms": ("spice", "masala", "sugar", "salt"),
        "catalogue": "/products?category=Groceries",
    },
    "/neemuch/rice-and-grains": {
        "title": "Rice & Grains in Neemuch | Grocery Shopping | Vibe4You",
        "description": "Shop rice and grains in Neemuch from local grocery stores. Compare current varieties, pack sizes and prices on Vibe4You.",
        "heading": "Rice & Grains in Neemuch",
        "intro": "Browse rice, grains and everyday pantry staples available from participating Neemuch grocery sellers.",
        "category": "Groceries",
        "subcategories": ("Rice & Other Grains", "Rice & Grains"),
        "terms": ("rice", "grain"),
        "catalogue": "/products?category=Groceries",
    },
    "/neemuch/jams-and-honey": {
        "title": "Jams, Honey & Spreads in Neemuch | Vibe4You",
        "description": "Shop jams, honey and spreads in Neemuch from local grocery stores. Compare current flavours, pack sizes and prices.",
        "heading": "Jams, Honey & Spreads in Neemuch",
        "intro": "Find jam, honey and breakfast spreads from participating Neemuch grocery sellers in one local catalogue.",
        "category": "Groceries",
        "subcategories": ("Jams, Honey & Spreads", "Jams & Honey"),
        "terms": ("jam", "honey", "spread"),
        "catalogue": "/products?category=Groceries",
    },
    "/neemuch/breakfast-cereals": {
        "title": "Breakfast Cereals in Neemuch | Grocery Shopping | Vibe4You",
        "description": "Shop breakfast cereals in Neemuch from local grocery stores. Compare current brands, pack sizes and prices on Vibe4You.",
        "heading": "Breakfast Cereals in Neemuch",
        "intro": "Browse cereal and breakfast products available from participating Neemuch grocery sellers.",
        "category": "Groceries",
        "subcategories": ("Breakfast Cereals",),
        "terms": ("breakfast cereal", "cereal"),
        "catalogue": "/products?category=Groceries&subcategory=Breakfast%20Cereals",
    },
    "/neemuch/oil-and-ghee": {
        "title": "Cooking Oil & Ghee in Neemuch | Grocery Shopping | Vibe4You",
        "description": "Shop cooking oil and ghee in Neemuch from local grocery stores. Compare current brands, pack sizes and prices on Vibe4You.",
        "heading": "Cooking Oil & Ghee in Neemuch",
        "intro": "Find cooking oils, edible oil and ghee from participating Neemuch grocery sellers and compare current local listings.",
        "category": "Groceries",
        "subcategories": ("Oils & Ghee", "Oil & Ghee"),
        "terms": ("cooking oil", "edible oil", "ghee"),
        "catalogue": "/products?category=Groceries",
    },
    "/neemuch/kitchen-appliances": {
        "title": "Kitchen Appliances in Neemuch | Shop Local Online | Vibe4You",
        "description": "Shop kitchen appliances in Neemuch from local home stores. Browse current appliances and compare prices on Vibe4You.",
        "heading": "Kitchen Appliances in Neemuch",
        "intro": "Browse kitchen appliances and useful kitchen machines available from participating Neemuch home and living stores.",
        "category": "Home & Living",
        "subcategories": ("Kitchen Appliances", "Home Appliances", "Kitchen & Utility"),
        "terms": ("kitchen appliance", "home appliance", "kitchen machine"),
        "catalogue": "/products?category=Home%20%26%20Living",
    },
    "/neemuch/toys": {
        "title": "Toys & Games in Neemuch | Kids Toys & Gifts | Vibe4You",
        "description": "Shop toys and games in Neemuch from local sellers. Browse remote-control toys, dolls, playsets, action figures and more.",
        "heading": "Toys & Games in Neemuch",
        "intro": "Find toys, games and children's gift items from Neemuch sellers, including remote-control toys, dolls, playsets and action figures.",
        "categories": ("Gifts", "Toys & Games"),
        "terms": ("toy", "game", "doll", "playset", "action figure", "remote control"),
        "catalogue": "/products?search=toys",
    },
})

# Keep every local landing title within the same 65-character guard used by
# the verified Bing remediation. These five pre-existing pages were already
# descriptive, but their full titles exceeded that release-wide limit.
NEEMUCH_LOCAL_PAGES["/neemuch/shoes"]["title"] = "Shoes in Neemuch | Sneakers & Footwear | Vibe4You"
NEEMUCH_LOCAL_PAGES["/neemuch/womens-clothing"]["title"] = "Women's Clothing in Neemuch | Tops, Jeans & Kurtas | Vibe4You"
NEEMUCH_LOCAL_PAGES["/neemuch/same-day-delivery"]["title"] = "Same Day Delivery in Neemuch | Shop Local | Vibe4You"
NEEMUCH_LOCAL_PAGES["/neemuch/shops"]["title"] = "Local Shops in Neemuch | Shop Online | Vibe4You"
NEEMUCH_LOCAL_PAGES["/neemuch/mobile-accessories"]["title"] = "Mobile Accessories in Neemuch | Chargers & Cables | Vibe4You"

_NEEMUCH_SEARCH_VARIANTS = {
    "/neemuch/shoes": (("Footwear", "/neemuch/shoes"), ("Shoe", "/neemuch/shoes"), ("Shoes", "/neemuch/shoes"), ("Sneakers", "/neemuch/sneakers"), ("Sports shoes", "/neemuch/sports-shoes"), ("Running shoes", "/neemuch/sports-shoes"), ("Slippers", "/neemuch/slippers"), ("Flip-flops", "/neemuch/slippers"), ("Sliders", "/neemuch/sliders"), ("Women's footwear", "/neemuch/womens-footwear")),
    "/neemuch/sneakers": (("Sneaker", "/neemuch/sneakers"), ("Sneakers", "/neemuch/sneakers"), ("Trainers", "/neemuch/sneakers"), ("Casual shoes", "/neemuch/shoes"), ("Sports sneakers", "/neemuch/sports-shoes")),
    "/neemuch/sports-shoes": (("Sports shoe", "/neemuch/sports-shoes"), ("Sports shoes", "/neemuch/sports-shoes"), ("Running shoe", "/neemuch/sports-shoes"), ("Running shoes", "/neemuch/sports-shoes"), ("Training shoes", "/neemuch/sports-shoes"), ("Athletic footwear", "/neemuch/sports-shoes")),
    "/neemuch/slippers": (("Slipper", "/neemuch/slippers"), ("Slippers", "/neemuch/slippers"), ("Flip-flop", "/neemuch/slippers"), ("Flip-flops", "/neemuch/slippers"), ("Chappal", "/neemuch/slippers"), ("Chappals", "/neemuch/slippers")),
    "/neemuch/sliders": (("Slider", "/neemuch/sliders"), ("Sliders", "/neemuch/sliders"), ("Slide", "/neemuch/sliders"), ("Slides", "/neemuch/sliders"), ("Slip-on footwear", "/neemuch/sliders")),
    "/neemuch/womens-footwear": (("Women's footwear", "/neemuch/womens-footwear"), ("Ladies footwear", "/neemuch/womens-footwear"), ("Women's shoes", "/neemuch/womens-footwear"), ("Flats", "/neemuch/womens-footwear"), ("Heels", "/neemuch/womens-footwear"), ("Sandals", "/neemuch/womens-footwear")),
    "/neemuch/clothes": (("Clothes", "/neemuch/clothes"), ("Clothing", "/neemuch/clothes"), ("Fashion", "/neemuch/clothes"), ("Apparel", "/neemuch/clothes"), ("Garments", "/neemuch/clothes"), ("T-shirts", "/neemuch/t-shirts"), ("Shirts", "/neemuch/shirts"), ("Jeans", "/neemuch/jeans")),
    "/neemuch/t-shirts": (("T-shirt", "/neemuch/t-shirts"), ("T-shirts", "/neemuch/t-shirts"), ("Tee", "/neemuch/t-shirts"), ("Tees", "/neemuch/t-shirts"), ("Polo T-shirt", "/neemuch/t-shirts")),
    "/neemuch/shirts": (("Shirt", "/neemuch/shirts"), ("Shirts", "/neemuch/shirts"), ("Casual shirts", "/neemuch/shirts"), ("Formal shirts", "/neemuch/shirts")),
    "/neemuch/jeans": (("Jean", "/neemuch/jeans"), ("Jeans", "/neemuch/jeans"), ("Denim", "/neemuch/jeans"), ("Denims", "/neemuch/jeans")),
    "/neemuch/watches": (("Watch", "/neemuch/watches"), ("Watches", "/neemuch/watches"), ("Wrist watch", "/neemuch/watches"), ("Analog watch", "/neemuch/watches"), ("Digital watch", "/neemuch/watches")),
    "/neemuch/jewellery": (("Jewellery", "/neemuch/jewellery"), ("Jewelry", "/neemuch/jewellery"), ("Fashion jewellery", "/neemuch/jewellery"), ("Artificial jewellery", "/neemuch/jewellery"), ("Earrings", "/neemuch/earrings"), ("Bangles", "/neemuch/jewellery"), ("Necklaces", "/neemuch/jewellery")),
    "/neemuch/earrings": (("Earring", "/neemuch/earrings"), ("Earrings", "/neemuch/earrings"), ("Jhumka", "/neemuch/earrings"), ("Jhumki", "/neemuch/earrings"), ("Fashion earrings", "/neemuch/earrings")),
    "/neemuch/beauty": (("Beauty products", "/neemuch/beauty"), ("Personal care", "/neemuch/beauty"), ("Cosmetics", "/neemuch/beauty"), ("Skin care", "/neemuch/skin-care"), ("Hair care", "/neemuch/shampoos"), ("Soap", "/neemuch/soaps"), ("Perfume", "/neemuch/perfumes"), ("Baby care", "/neemuch/baby-care")),
    "/neemuch/shampoos": (("Shampoo", "/neemuch/shampoos"), ("Shampoos", "/neemuch/shampoos"), ("Hair shampoo", "/neemuch/shampoos"), ("Hair cleanser", "/neemuch/shampoos"), ("Conditioner", "/neemuch/shampoos")),
    "/neemuch/soaps": (("Soap", "/neemuch/soaps"), ("Soaps", "/neemuch/soaps"), ("Bath soap", "/neemuch/soaps"), ("Soap bars", "/neemuch/soaps"), ("Body wash", "/neemuch/soaps")),
    "/neemuch/baby-care": (("Baby care", "/neemuch/baby-care"), ("Baby products", "/neemuch/baby-care"), ("Diapers", "/neemuch/baby-care"), ("Baby wipes", "/neemuch/baby-care"), ("Baby skin care", "/neemuch/baby-care"), ("Baby shampoo", "/neemuch/baby-care")),
    "/neemuch/skin-care": (("Skin care", "/neemuch/skin-care"), ("Skincare", "/neemuch/skin-care"), ("Face wash", "/neemuch/skin-care"), ("Moisturizer", "/neemuch/skin-care"), ("Face serum", "/neemuch/skin-care"), ("Sunscreen", "/neemuch/skin-care")),
    "/neemuch/perfumes": (("Perfume", "/neemuch/perfumes"), ("Perfumes", "/neemuch/perfumes"), ("Fragrance", "/neemuch/perfumes"), ("Body spray", "/neemuch/perfumes"), ("Deodorant", "/neemuch/perfumes"), ("Deo", "/neemuch/perfumes")),
    "/neemuch/electronics": (("Electronics", "/neemuch/electronics"), ("Electronic products", "/neemuch/electronics"), ("Mobile phones", "/neemuch/mobile-phones"), ("Smartphones", "/neemuch/mobile-phones"), ("Phone covers", "/neemuch/mobile-covers"), ("Mobile accessories", "/neemuch/mobile-accessories")),
    "/neemuch/mobile-phones": (("Mobile", "/neemuch/mobile-phones"), ("Mobile phone", "/neemuch/mobile-phones"), ("Cell phone", "/neemuch/mobile-phones"), ("Smartphone", "/neemuch/mobile-phones"), ("Handset", "/neemuch/mobile-phones")),
    "/neemuch/mobile-covers": (("Mobile cover", "/neemuch/mobile-covers"), ("Mobile covers", "/neemuch/mobile-covers"), ("Phone cover", "/neemuch/mobile-covers"), ("Back cover", "/neemuch/mobile-covers"), ("Phone case", "/neemuch/mobile-covers"), ("Mobile case", "/neemuch/mobile-covers")),
    "/neemuch/mobile-accessories": (("Mobile accessories", "/neemuch/mobile-accessories"), ("Phone accessories", "/neemuch/mobile-accessories"), ("Chargers", "/neemuch/mobile-accessories"), ("Cables", "/neemuch/mobile-accessories"), ("Earphones", "/neemuch/mobile-accessories"), ("Power banks", "/neemuch/mobile-accessories")),
    "/neemuch/handbags": (("Handbag", "/neemuch/handbags"), ("Handbags", "/neemuch/handbags"), ("Ladies bag", "/neemuch/handbags"), ("Sling bag", "/neemuch/handbags"), ("Purse", "/neemuch/handbags")),
    "/neemuch/groceries": (("Grocery", "/neemuch/groceries"), ("Groceries", "/neemuch/groceries"), ("Kirana", "/neemuch/groceries"), ("Ration", "/neemuch/groceries"), ("Daily essentials", "/neemuch/groceries"), ("Tea and coffee", "/neemuch/tea-and-coffee"), ("Spices", "/neemuch/spices"), ("Rice and grains", "/neemuch/rice-and-grains")),
    "/neemuch/tea-and-coffee": (("Tea", "/neemuch/tea-and-coffee"), ("Chai", "/neemuch/tea-and-coffee"), ("Coffee", "/neemuch/tea-and-coffee"), ("Tea and coffee", "/neemuch/tea-and-coffee")),
    "/neemuch/spices": (("Spice", "/neemuch/spices"), ("Spices", "/neemuch/spices"), ("Masala", "/neemuch/spices"), ("Sugar", "/neemuch/spices"), ("Salt", "/neemuch/spices")),
    "/neemuch/rice-and-grains": (("Rice", "/neemuch/rice-and-grains"), ("Grain", "/neemuch/rice-and-grains"), ("Grains", "/neemuch/rice-and-grains"), ("Rice and grains", "/neemuch/rice-and-grains")),
    "/neemuch/jams-and-honey": (("Jam", "/neemuch/jams-and-honey"), ("Jams", "/neemuch/jams-and-honey"), ("Honey", "/neemuch/jams-and-honey"), ("Spreads", "/neemuch/jams-and-honey")),
    "/neemuch/breakfast-cereals": (("Breakfast cereal", "/neemuch/breakfast-cereals"), ("Breakfast cereals", "/neemuch/breakfast-cereals"), ("Cereal", "/neemuch/breakfast-cereals"), ("Cereals", "/neemuch/breakfast-cereals")),
    "/neemuch/oil-and-ghee": (("Cooking oil", "/neemuch/oil-and-ghee"), ("Edible oil", "/neemuch/oil-and-ghee"), ("Oil", "/neemuch/oil-and-ghee"), ("Ghee", "/neemuch/oil-and-ghee")),
    "/neemuch/home-and-living": (("Home products", "/neemuch/home-and-living"), ("Kitchen products", "/neemuch/home-and-living"), ("Household products", "/neemuch/home-and-living"), ("Home appliances", "/neemuch/kitchen-appliances"), ("Kitchen appliances", "/neemuch/kitchen-appliances"), ("Home essentials", "/neemuch/home-and-living")),
    "/neemuch/kitchen-appliances": (("Kitchen appliance", "/neemuch/kitchen-appliances"), ("Kitchen appliances", "/neemuch/kitchen-appliances"), ("Home appliance", "/neemuch/kitchen-appliances"), ("Kitchen machine", "/neemuch/kitchen-appliances")),
    "/neemuch/gifts": (("Gift", "/neemuch/gifts"), ("Gifts", "/neemuch/gifts"), ("Gift hamper", "/neemuch/gifts"), ("Gift box", "/neemuch/gifts"), ("Toys", "/neemuch/toys"), ("Games", "/neemuch/toys")),
    "/neemuch/toys": (("Toy", "/neemuch/toys"), ("Toys", "/neemuch/toys"), ("Games", "/neemuch/toys"), ("Kids toys", "/neemuch/toys"), ("Remote-control toys", "/neemuch/toys"), ("Dolls", "/neemuch/toys")),
}
for _path, _variants in _NEEMUCH_SEARCH_VARIANTS.items():
    if _path in NEEMUCH_LOCAL_PAGES:
        NEEMUCH_LOCAL_PAGES[_path]["searches"] = _variants
del _path, _variants

SPA_PAGE_SEO = {
    "/products": {
        "title": "Shop Products from Neemuch Stores | Vibe4You",
        "description": "Browse fashion, footwear, watches, electronics, groceries, beauty and gifts from local Neemuch stores on Vibe4You. Check current prices, availability and delivery serviceability.",
        "heading": "Products from Neemuch Stores",
    },
    "/": {
        "title": "Vibe4You | Shop Local Neemuch Stores with Same Day Delivery",
        "description": "Vibe4You brings Neemuch's local shops online. Shop fashion, footwear, watches, electronics, groceries, beauty and gifts from nearby stores with Same Day Delivery in Neemuch.",
        "heading": "Shop Local Neemuch Stores Online",
    },
    "/stores": {
        "title": "Local Stores in Neemuch | Shops on Vibe4You",
        "description": "Browse local stores in Neemuch on Vibe4You. Discover fashion, footwear, electronics, groceries, beauty and gift shops and order online with Same Day Delivery in supported areas.",
        "heading": "Local Boutiques and Partner Stores in Neemuch",
    },
    "/categories": {
        "title": "Shopping Categories in Neemuch | Vibe4You",
        "description": "Shop by category from local Neemuch stores on Vibe4You: clothing, footwear, watches, bags, electronics, groceries, beauty, home and gifts with Same Day Delivery in supported areas.",
        "heading": "Shopping Categories in Neemuch",
    },
    "/privacy": {
        "title": "Privacy Notice | Vibe4You",
        "description": "Read how Vibe4You handles customer account, order, payment, support and delivery information.",
        "heading": "Privacy Notice",
        "schema_type": "WebPage",
    },
    "/terms": {
        "title": "Terms and Conditions | Vibe4You",
        "description": "Read the Vibe4You terms for accounts, orders, pricing, delivery, payments, cancellations, returns and customer responsibilities.",
        "heading": "Terms and Conditions",
        "schema_type": "WebPage",
    },
    "/returns": {
        "title": "Returns and Exchanges | Vibe4You",
        "description": "Review Vibe4You return, size exchange, cancellation, pickup charge and refund policies for eligible orders.",
        "heading": "Returns and Exchanges",
        "schema_type": "WebPage",
    },
    "/help": {
        "title": "Help and Customer Support | Vibe4You",
        "description": "Get help with Vibe4You orders, payments, delivery, cancellations, returns and exchanges.",
        "heading": "Help and Customer Support",
        "schema_type": "WebPage",
    },
}

# Keep the server-side status code aligned with the client router. Unknown
# extensionless paths must not receive the SPA shell with HTTP 200 because that
# creates indexable soft-404s. Dynamic catalogue routes are additionally
# verified against the published product/store data before this allowlist is
# consulted.
SPA_EXACT_ROUTES = frozenset({
    "/", "/products", "/categories", "/offers", "/stores", "/partner",
    "/wishlist", "/login", "/register", "/forgot-password",
    "/reset-password", "/checkout", "/orders", "/delivery-requests",
    "/profile", "/help", "/returns", "/privacy", "/terms",
    "/payment-test/styledash-payment-test-item",
})
SPA_DYNAMIC_ROUTE_PATTERNS = (
    re.compile(r"/order-success/[^/]{1,128}"),
    re.compile(r"/orders/[^/]{1,128}/track"),
)



def _homepage_sort_key(product: dict[str, Any]) -> tuple:
    created = product.get("createdAt") or ""
    score = (
        (50 if product.get("featured") else 0)
        + (30 if product.get("trending") else 0)
        + (20 if product.get("newArrival") else 0)
        + round(float(product.get("rating") or 0) * 5)
        + min(int(product.get("reviewCount") or 0), 20)
    )
    return (score, created, str(product.get("name") or ""))


def _homepage_product_candidates(products: list[dict[str, Any]], per_section: int = 10) -> list[dict[str, Any]]:
    active = [product for product in products if product.get("active") is True]
    definitions = (
        lambda p: p.get("category") == "Clothing & Fashion",
        lambda p: p.get("category") == "Footwear",
        lambda p: p.get("category") == "Accessories" or p.get("department") == "accessories",
        lambda p: p.get("category") == "Beauty & Personal Care",
        lambda p: p.get("category") == "Electronics",
        lambda p: p.get("category") == "Gifts",
        lambda p: p.get("category") == "Home & Living",
        lambda p: p.get("department") == "women",
        lambda p: p.get("department") == "men",
        lambda p: p.get("newArrival") is True,
        lambda p: p.get("trending") is True,
        lambda p: float(p.get("price") or 0) <= 499,
        lambda p: True,
    )
    selected: dict[str, dict[str, Any]] = {}
    # Sort once; every section shares the same ordering key, so filter the
    # pre-sorted list instead of re-sorting per section.
    ordered = sorted(active, key=_homepage_sort_key, reverse=True)
    for matches in definitions:
        candidates = [p for p in ordered if matches(p)]
        # Prefer store diversity (max 2 per store), then top up without that
        # cap so a section still reaches `per_section` whenever that many
        # eligible candidates exist.
        section_choices: list[dict[str, Any]] = []
        chosen_ids: set[str] = set()
        store_counts: dict[str, int] = defaultdict(int)
        for allow_repeat_store in (False, True):
            for product in candidates:
                product_id = str(product["id"])
                if product_id in chosen_ids:
                    continue
                store = str(product.get("vendorId") or product.get("storeSlug") or "")
                if not allow_repeat_store and store_counts[store] >= 2:
                    continue
                section_choices.append(product)
                chosen_ids.add(product_id)
                store_counts[store] += 1
                if len(section_choices) >= per_section:
                    break
            if len(section_choices) >= per_section:
                break
        for product in section_choices:
            selected[str(product["id"])] = product
    return list(selected.values())


def _homepage_product_projection(product: dict[str, Any]) -> dict[str, Any]:
    projected = dict(product)
    images = list(product.get("images") or [])
    projected["images"] = images[:2]
    projected["description"] = ""
    projected["shortDescription"] = ""
    projected["material"] = ""
    projected["careInstructions"] = []
    projected["tags"] = []
    projected["variants"] = [
        {
            "id": variant.get("id"),
            "sku": variant.get("sku") or "",
            "size": variant.get("size") or "",
            "colourName": variant.get("colourName") or "",
            "colourHex": variant.get("colourHex"),
            "stock": 0,
        }
        for variant in product.get("variants", [])
    ]
    return projected




def _validate_png(content: bytes) -> bool:
    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
        return False
    offset = 8
    seen_ihdr = False
    seen_iend = False
    while offset + 12 <= len(content):
        length = struct.unpack(">I", content[offset : offset + 4])[0]
        chunk_type = content[offset + 4 : offset + 8]
        data_start = offset + 8
        data_end = data_start + length
        crc_end = data_end + 4
        if crc_end > len(content):
            return False
        expected_crc = struct.unpack(">I", content[data_end:crc_end])[0]
        actual_crc = zlib.crc32(chunk_type + content[data_start:data_end]) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            return False
        if not seen_ihdr:
            if chunk_type != b"IHDR" or length != 13:
                return False
            width, height = struct.unpack(">II", content[data_start : data_start + 8])
            if width < 1 or height < 1 or width > 12000 or height > 12000:
                return False
            seen_ihdr = True
        if chunk_type == b"IEND":
            if length != 0 or crc_end != len(content):
                return False
            seen_iend = True
            break
        offset = crc_end
    return seen_ihdr and seen_iend


def _validate_webp(content: bytes) -> bool:
    if len(content) < 20 or content[:4] != b"RIFF" or content[8:12] != b"WEBP":
        return False
    if struct.unpack("<I", content[4:8])[0] != len(content) - 8:
        return False
    offset = 12
    image_chunk = False
    while offset + 8 <= len(content):
        chunk_type = content[offset : offset + 4]
        chunk_size = struct.unpack("<I", content[offset + 4 : offset + 8])[0]
        data_end = offset + 8 + chunk_size
        padded_end = data_end + (chunk_size & 1)
        if data_end > len(content) or padded_end > len(content):
            return False
        if chunk_type in {b"VP8 ", b"VP8L", b"ANMF"}:
            image_chunk = True
        offset = padded_end
    return image_chunk and offset == len(content)


def _validate_jpeg(content: bytes) -> bool:
    if len(content) < 16 or not content.startswith(b"\xff\xd8") or not content.endswith(b"\xff\xd9"):
        return False
    offset = 2
    saw_frame = False
    frame_markers = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    while offset < len(content) - 2:
        if content[offset] != 0xFF:
            return False
        while offset < len(content) and content[offset] == 0xFF:
            offset += 1
        if offset >= len(content):
            return False
        marker = content[offset]
        offset += 1
        if marker == 0xD9:
            return saw_frame and offset == len(content)
        if marker == 0xDA:
            return saw_frame and content.endswith(b"\xff\xd9")
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:
            continue
        if offset + 2 > len(content):
            return False
        segment_length = struct.unpack(">H", content[offset : offset + 2])[0]
        if segment_length < 2 or offset + segment_length > len(content):
            return False
        if marker in frame_markers:
            if segment_length < 8:
                return False
            height, width = struct.unpack(">HH", content[offset + 3 : offset + 7])
            if width < 1 or height < 1 or width > 12000 or height > 12000:
                return False
            saw_frame = True
        offset += segment_length
    return False


def store_product_image_payload(product_image_directory: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) != {"fileName", "contentType", "dataBase64"}:
        raise SecurityError(400, "Invalid image upload.", "invalid_product_image")
    file_name = payload.get("fileName")
    content_type = payload.get("contentType")
    encoded = payload.get("dataBase64")
    if (
        not isinstance(file_name, str)
        or not 1 <= len(file_name) <= 120
        or "/" in file_name
        or "\\" in file_name
        or any(ord(character) < 32 for character in file_name)
    ):
        raise SecurityError(400, "Invalid image filename.", "invalid_product_image")
    extensions = {"image/webp": "webp", "image/jpeg": "jpg", "image/png": "png"}
    validators = {"image/webp": _validate_webp, "image/jpeg": _validate_jpeg, "image/png": _validate_png}
    extension = extensions.get(content_type)
    if extension is None or not isinstance(encoded, str) or not encoded:
        raise SecurityError(400, "Upload a JPEG, PNG or WebP image.", "invalid_product_image")
    try:
        content = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise SecurityError(400, "Invalid image data.", "invalid_product_image") from None
    if not 32 <= len(content) <= PRODUCT_IMAGE_MAX_BYTES:
        raise SecurityError(413, "The optimized image must be 500 KB or smaller.", "product_image_too_large")
    if not validators[content_type](content):
        raise SecurityError(400, "The uploaded file does not match its image type.", "invalid_product_image")
    product_image_directory.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(product_image_directory, 0o700)
    except OSError:
        pass
    digest = hashlib.sha256(content).hexdigest()[:32]
    target = product_image_directory / f"{digest}.{extension}"
    if not target.exists():
        temporary = product_image_directory / f".{digest}.{secrets.token_hex(6)}.tmp"
        temporary.write_bytes(content)
        try:
            os.chmod(temporary, 0o644)
        except OSError:
            pass
        os.replace(temporary, target)
    return {"url": f"/media/product-images/{target.name}", "bytes": len(content), "contentType": content_type}
# Firebase/Google endpoints are added narrowly (never a wildcard) and only to
# support the Google + Phone-OTP identity flows; Firebase is never granted
# order/payment/inventory/admin authority.
SECURITY_POLICY = (
    "default-src 'self'; "
    "base-uri 'self'; object-src 'none'; frame-ancestors 'self'; "
    "script-src 'self' 'sha256-7x4x3jtoyTNeq0JRGa3FwU2a/aq5BH/my3RjlQnEmZg=' https://checkout.razorpay.com https://*.razorpay.com "
    "https://apis.google.com https://www.gstatic.com https://www.google.com https://www.recaptcha.net "
    "https://static.cloudflareinsights.com https://www.googletagmanager.com https://connect.facebook.net; "
    "style-src 'self' 'unsafe-inline' https://*.razorpay.com; "
    "img-src 'self' data: https:; font-src 'self' data: https:; "
    "connect-src 'self' https://api.razorpay.com https://*.razorpay.com "
    "https://identitytoolkit.googleapis.com https://securetoken.googleapis.com https://www.googleapis.com "
    "https://*.firebaseio.com wss://*.firebaseio.com https://cloudflareinsights.com "
    "https://www.google-analytics.com https://analytics.google.com https://region1.google-analytics.com "
    "https://www.facebook.com; "
    "frame-src https://api.razorpay.com https://checkout.razorpay.com https://*.razorpay.com "
    "https://accounts.google.com https://*.firebaseapp.com https://www.google.com https://www.recaptcha.net; "
    "form-action 'self' https://api.razorpay.com https://*.razorpay.com"
)
HSTS_POLICY = "max-age=31536000"
ACCESS_LOG_TOKEN_PATTERN = re.compile(r"([?&](?:token|reset_token)=)[^&#\s]*", re.IGNORECASE)
PAYMENT_TEST_PRODUCT_ID = "styledash-payment-test-item"
PAYMENT_TEST_PRODUCT_SLUG = "styledash-payment-test-item"
PAYMENT_TEST_ROUTE = f"/payment-test/{PAYMENT_TEST_PRODUCT_SLUG}"
PAYMENT_TEST_PRODUCT_NAME = "Vibe4You Payment Test Item"
PAYMENT_TEST_VARIANT_ID = "styledash-payment-test-item-validation"
PAYMENT_TEST_PRICE_RUPEES = 10
PAYMENT_TEST_AMOUNT_PAISE = 1000
PAYMENT_TEST_CURRENCY = "INR"
PAYMENT_TEST_ADMIN_LABELS = ["TEST", "NO FULFILLMENT REQUIRED"]
LOW_STOCK_THRESHOLD = 5
COD_ADVANCE_RUPEES = 50
COD_ADVANCE_PAISE = COD_ADVANCE_RUPEES * 100


def _notify_finalized_payment(order: dict[str, Any]) -> None:
    """Best-effort owner notification after captured payment is durable."""

    try:
        order_id = str(order.get("id") or "-")
        grand_total = order.get("grandTotal")

        amount_text = (
            f"?{grand_total}"
            if isinstance(grand_total, (int, float))
            and not isinstance(grand_total, bool)
            else "-"
        )

        is_cod_advance = order.get("paymentMethod") == "cod" and order.get("codAdvancePaid") is True
        payment_method = "COD ADVANCE" if is_cod_advance else str(order.get("paymentMethod") or "online").upper()

        status = order.get("status")

        if status == "payment_review_required":
            owner_notifier().send(
                event="payment_review_required",
                title="PAYMENT NEEDS ATTENTION",
                message=(
                    f"Order: {order_id}\n"
                    f"Amount: {amount_text}\n"
                    f"Payment: {payment_method}\n"
                    f"Status: Paid - review required\n"
                    f"Reason: Stock confirmation required"
                ),
                priority=5,
                tags=["rotating_light"],
            )
            return

        owner_notifier().send(
            event="cod_advance_captured" if is_cod_advance else "payment_captured",
            title="Vibe4You COD Advance Received" if is_cod_advance else "Vibe4You Payment Received",
            message=(
                f"Order: {order_id}\n"
                f"Amount: {'Rs ' + str(order.get('codAdvanceAmount')) if is_cod_advance else amount_text}\n"
                f"Payment: {payment_method}\n"
                f"Status: {'COD balance due: Rs ' + str(order.get('codAmountDue')) if is_cod_advance else 'Paid'}"
            ),
            priority=5,
            tags=["moneybag"],
        )

    except Exception:
        # Notification preparation must never affect financial truth.
        print(
            "Vibe4You notification preparation failed "
            "event=payment_captured",
            flush=True,
        )


def _notify_cod_order_placed(order: dict[str, Any]) -> None:
    """Best-effort owner notification after a Cash on Delivery order is durable."""

    try:
        order_id = str(order.get("id") or "-")
        grand_total = order.get("grandTotal")
        amount_text = (
            f"Rs {grand_total}"
            if isinstance(grand_total, (int, float))
            and not isinstance(grand_total, bool)
            else "-"
        )
        owner_notifier().send(
            event="cod_order_placed",
            title="Vibe4You New COD Order",
            message=(
                f"Order: {order_id}\n"
                f"Amount: {amount_text}\n"
                f"Payment: COD (no advance)\n"
                f"Status: Collect {amount_text} on delivery"
            ),
            priority=5,
            tags=["package"],
        )
    except Exception:
        # Notification preparation must never affect a durable order.
        print(
            "Vibe4You notification preparation failed "
            "event=cod_order_placed",
            flush=True,
        )


def _notify_shop_product_review(*, result: dict[str, Any], event: str, title: str, request_type: str = "") -> None:
    try:
        product_id = str(result.get("productId") or result.get("id") or "-")[:120]
        product_name = " ".join(str(result.get("productName") or result.get("name") or "-").split())[:120]
        category = " ".join(str(result.get("category") or "-").split())[:80]
        status = " ".join(str(result.get("status") or "-").split())[:40]
        lines = [f"Product: {product_name}", f"Reference: {product_id}"]
        if request_type:
            lines.append(f"Request: {request_type}")
        elif category != "-":
            lines.append(f"Category: {category}")
        lines.append(f"Status: {status}")
        owner_notifier().send(event=event, title=title, message="\n".join(lines), priority=5, tags=["package"])
    except Exception:
        print(f"Vibe4You notification preparation failed event={event}", flush=True)


def _notify_inventory_alerts(
    alerts: list[dict[str, Any]],
) -> None:
    """Send inventory threshold alerts only after durable persistence."""

    for alert in alerts:
        try:
            kind = alert.get("kind")

            if kind == "out_of_stock":
                event = "inventory_out_of_stock"
                title = "Vibe4You Out of Stock"
                tags = ["rotating_light"]
            elif kind == "low_stock":
                event = "inventory_low_stock"
                title = "Vibe4You Low Stock"
                tags = ["warning"]
            else:
                continue

            product_name = " ".join(
                str(alert.get("productName") or "-").split()
            )[:120]

            size = " ".join(
                str(alert.get("size") or "-").split()
            )[:40]

            colour = " ".join(
                str(alert.get("colour") or "-").split()
            )[:80]

            remaining = alert.get("remaining")

            owner_notifier().send(
                event=event,
                title=title,
                message=(
                    f"Product: {product_name}\n"
                    f"Variant: {size} / {colour}\n"
                    f"Remaining: {remaining}"
                ),
                priority=5,
                tags=tags,
            )

        except Exception:
            print(
                "Vibe4You notification preparation failed "
                "event=inventory",
                flush=True,
            )


class ApiError(Exception):
    def __init__(self, status: int, message: str, code: str = "request_failed") -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.code = code


ADMIN_REFUND_TOKEN_FILENAME = ".admin-refund-token"


def ensure_admin_refund_token(data_directory: Path) -> str:
    """Return a private cross-process token used only on the loopback refund bridge."""
    data_directory.mkdir(parents=True, exist_ok=True)
    path = data_directory / ADMIN_REFUND_TOKEN_FILENAME

    def read_existing() -> str:
        try:
            token = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeError("The private admin refund token could not be read") from exc
        if not 40 <= len(token) <= 256 or any(character.isspace() for character in token):
            raise RuntimeError("The private admin refund token is invalid")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return token

    if path.exists():
        return read_existing()

    token = secrets.token_urlsafe(48)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return read_existing()
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(token + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    os.chmod(path, 0o600)
    return token


class RazorpayGateway:
    """Small adapter that keeps SDK details out of the order service."""

    def __init__(self, key_id: str, key_secret: str) -> None:
        if razorpay is None:
            raise RuntimeError("The Razorpay Python package is not installed")
        self.client = razorpay.Client(auth=(key_id, key_secret))

    def create_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.client.order.create(data=payload)
        except Exception as exc:  # Razorpay SDK exceptions expose status_code.
            status = int(getattr(exc, "status_code", 500) or 500)
            if status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                raise ApiError(
                    HTTPStatus.UNAUTHORIZED,
                    "Payment service authentication failed.",
                    "payment_auth_failed",
                ) from None
            raise ApiError(
                HTTPStatus.BAD_GATEWAY,
                "The payment service is temporarily unavailable.",
                "payment_service_unavailable",
            ) from None

    def fetch_payment(self, payment_id: str) -> dict[str, Any]:
        try:
            return self.client.payment.fetch(payment_id)
        except Exception as exc:  # Razorpay SDK exceptions expose status_code.
            status = int(getattr(exc, "status_code", 500) or 500)
            if status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                raise ApiError(
                    HTTPStatus.UNAUTHORIZED,
                    "Payment service authentication failed.",
                    "payment_auth_failed",
                ) from None
            raise ApiError(
                HTTPStatus.BAD_GATEWAY,
                "The payment service is temporarily unavailable.",
                "payment_service_unavailable",
            ) from None

    def create_refund(self, payment_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.client.payment.refund(payment_id, data=payload)
        except Exception as exc:  # Razorpay SDK exceptions expose status_code.
            status = int(getattr(exc, "status_code", 500) or 500)
            if status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                raise ApiError(
                    HTTPStatus.UNAUTHORIZED,
                    "Refund service authentication failed.",
                    "payment_auth_failed",
                ) from None
            if 400 <= status < 500 and status != HTTPStatus.TOO_MANY_REQUESTS:
                raise ApiError(
                    HTTPStatus.CONFLICT,
                    "Razorpay rejected the refund request. Check the payment and available balance before retrying.",
                    "refund_rejected",
                ) from None
            raise ApiError(
                HTTPStatus.BAD_GATEWAY,
                "The refund service is temporarily unavailable. The refund outcome is not confirmed.",
                "refund_service_unavailable",
            ) from None


class StateFileLock:
    """Thread lock plus Termux process lock; reloads state after acquisition."""

    def __init__(self, owner: "JsonStateStore") -> None:
        self.owner = owner
        self.thread_lock = threading.RLock()
        self.handle = None
        self.depth = 0

    def __enter__(self):
        self.thread_lock.acquire()
        if self.depth:
            self.depth += 1
            return self
        try:
            self.owner.lock_path.parent.mkdir(parents=True, exist_ok=True)
            self.handle = self.owner.lock_path.open("a+b")
            os.chmod(self.owner.lock_path, 0o600)
            if fcntl is not None:
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
            self.owner.state = self.owner._load()
            self.depth = 1
            return self
        except Exception:
            if self.handle:
                self.handle.close()
                self.handle = None
            self.thread_lock.release()
            raise

    def __exit__(self, exc_type, exc_value, traceback):
        self.depth -= 1
        if self.depth:
            self.thread_lock.release()
            return
        try:
            if self.handle and fcntl is not None:
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            if self.handle:
                self.handle.close()
                self.handle = None
        finally:
            self.thread_lock.release()


class JsonStateStore:
    """Thread-safe JSON persistence using atomic replacement."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.path.with_suffix(f"{self.path.suffix}.lock")
        self.state = self._load()
        self.lock = StateFileLock(self)

    def _load(self) -> dict[str, Any]:
        default = {
            "orders": {},
            "inventory": {},
            "idempotency": {},
            "processedPayments": {},
            "processedRefunds": {},
            "processedWebhookEvents": {},
            "operationalAlerts": {},
            "deliveryRequests": {},
        }
        if not self.path.exists():
            return default
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise RuntimeError("Vibe4You payment state is not a JSON object")
            for key, value in default.items():
                loaded.setdefault(key, value)
            for order_id, order in loaded["orders"].items():
                payment_id = order.get("razorpayPaymentId") if isinstance(order, dict) else None
                if payment_id and order.get("paymentStatus") == "paid":
                    loaded["processedPayments"].setdefault(payment_id, order_id)
            return loaded
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("Vibe4You payment state could not be loaded safely") from exc

    def save(self) -> None:
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(self.state, handle, separators=(",", ":"), ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, self.path)
        os.chmod(self.path, 0o600)


# Rate-limit client identity (V4Y-049). The socket peer is the default. Only
# when the owner explicitly sets STYLEDASH_CLIENT_IP_SOURCE=cloudflare AND the
# request arrives from loopback (cloudflared) is Cloudflare's CF-Connecting-IP
# used; Cloudflare overwrites that header at its edge. X-Forwarded-For is never
# used for identity because its first hop is client-controlled.
CLIENT_IP_SOURCE_ENV = "STYLEDASH_CLIENT_IP_SOURCE"
CLIENT_IP_SOURCE_CLOUDFLARE = "cloudflare"
LOOPBACK_PEERS = ("127.0.0.1", "::1")
CF_CONNECTING_IP_MAX_LENGTH = 45


def cloudflare_client_identity(values: list[str] | None) -> str | None:
    """Return a rate-limit identity from exactly one valid CF-Connecting-IP value.

    Anything other than a single bare IPv4/IPv6 address (lists, ports,
    brackets, zone IDs, empty or over-long values, repeated headers) is
    rejected so the caller falls back to the socket peer. IPv6 visitors are
    grouped by their /64 network to stop trivial address rotation.
    """
    if not values or len(values) != 1 or not isinstance(values[0], str):
        return None
    candidate = values[0].strip()
    if (
        not candidate
        or len(candidate) > CF_CONNECTING_IP_MAX_LENGTH
        or not candidate.isascii()
        or "%" in candidate
    ):
        return None
    try:
        address = ipaddress.ip_address(candidate)
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None:
            return str(address.ipv4_mapped)
        return str(ipaddress.IPv6Network((address, 64), strict=False))
    return str(address)


class RateLimiter:
    """Sliding-window limiter with bounded memory (V4Y-049).

    Decisions for any key that is present are identical to the original
    limiter. Memory is bounded three ways, all under the existing lock:
    * keys are created only for allowed requests and dropped as soon as
      pruning empties them;
    * keys are ordered by their newest event, so a periodic sweep removes
      idle keys (newest event older than the longest window ever used) from
      the front in amortised O(removed) time; such a removal cannot change
      any later decision;
    * at most ``max_keys`` keys exist. A live key is never evicted (that
      would reset its limit, i.e. a bypass). When the map is still full of
      live keys after a sweep, a new client is limited through a coarse
      shared per-route overflow bucket instead (fail closed).
    """

    MAX_KEYS = 100_000
    SWEEP_INTERVAL_SECONDS = 60.0
    OVERFLOW_PREFIX = "rate-limit-overflow:"

    def __init__(
        self,
        max_keys: int = MAX_KEYS,
        sweep_interval_seconds: float = SWEEP_INTERVAL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._events: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.Lock()
        self._max_keys = max(1, int(max_keys))
        self._sweep_interval = float(sweep_interval_seconds)
        self._clock = clock
        self._max_window = 0.0
        self._next_sweep = clock() + self._sweep_interval

    def __len__(self) -> int:
        with self._lock:
            return len(self._events)

    @classmethod
    def _overflow_key(cls, key: str) -> str:
        # Route labels are server-defined constants, so this set is small.
        return cls.OVERFLOW_PREFIX + key.split(":", 1)[0]

    def _sweep(self, now: float) -> None:
        horizon = now - self._max_window
        while self._events:
            key, events = next(iter(self._events.items()))
            if events and events[-1] >= horizon:
                break
            del self._events[key]
        self._next_sweep = now + self._sweep_interval

    def allow(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        now = self._clock()
        cutoff = now - window_seconds
        with self._lock:
            if window_seconds > self._max_window:
                self._max_window = float(window_seconds)
            if now >= self._next_sweep:
                self._sweep(now)
            events = self._events.get(key)
            if events is None and len(self._events) >= self._max_keys:
                self._sweep(now)
                if len(self._events) >= self._max_keys:
                    key = self._overflow_key(key)
                    events = self._events.get(key)
            if events is not None:
                while events and events[0] < cutoff:
                    events.popleft()
                if len(events) >= limit:
                    if not events:
                        del self._events[key]
                    return False
            elif limit <= 0:
                return False
            else:
                events = deque()
                self._events[key] = events
            events.append(now)
            self._events.move_to_end(key)
            return True


def _money(value: Any, field: str) -> Decimal:
    if isinstance(value, bool):
        raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, f"Invalid {field}.", "invalid_cart")
    try:
        result = Decimal(str(value))
    except Exception:
        raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, f"Invalid {field}.", "invalid_cart") from None
    if not result.is_finite() or result < 0:
        raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, f"Invalid {field}.", "invalid_cart")
    return result


def _rounded_rupees(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _rounded_tax_rupees(value: Decimal) -> float:
    """Keep the approved Phase 1 disclosure at paisa precision.

    The established generic product-GST branch below deliberately retains its
    own whole-rupee presentation semantics.  This helper is only used by the
    explicit exact-ID Phase 1 policy path.
    """
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _pdf_escape(value: Any) -> str:
    text = str(value or "").encode("latin-1", "replace").decode("latin-1")
    text = "".join(character if ord(character) >= 32 else " " for character in text)
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _simple_pdf(lines: list[str]) -> bytes:
    wrapped: list[str] = []
    for line in lines:
        text = str(line or "")
        if not text:
            wrapped.append("")
            continue
        while len(text) > 88:
            split = text.rfind(" ", 0, 89)
            split = split if split > 20 else 88
            wrapped.append(text[:split].rstrip())
            text = text[split:].lstrip()
        wrapped.append(text)
    pages = [wrapped[index:index + 38] for index in range(0, len(wrapped), 38)] or [[""]]
    font_number = 3 + (2 * len(pages))
    kids = " ".join(f"{3 + (2 * index)} 0 R" for index in range(len(pages)))
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode(),
    ]
    for index, page_lines in enumerate(pages):
        page_number = 3 + (2 * index)
        content_number = page_number + 1
        commands = ["BT", "/F1 11 Tf", "48 760 Td"]
        for line_index, line in enumerate(page_lines):
            if line_index:
                commands.append("0 -17 Td")
            commands.append(f"({_pdf_escape(line)}) Tj")
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1", "replace")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font_number} 0 R >> >> /Contents {content_number} 0 R >>".encode())
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(pdf)); pdf.extend(f"{number} 0 obj\n".encode()); pdf.extend(obj); pdf.extend(b"\nendobj\n")
    xref = len(pdf); pdf.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]: pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(pdf)


def _clean_string(value: Any, field: str, minimum: int, maximum: int) -> str:
    if not isinstance(value, str):
        raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, f"Invalid {field}.", "invalid_customer")
    cleaned = value.strip()
    if not minimum <= len(cleaned) <= maximum:
        raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, f"Invalid {field}.", "invalid_customer")
    return cleaned


def _is_six_ascii_digits(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 6
        and all("0" <= character <= "9" for character in value)
    )


class PaymentService:
    def __init__(
        self,
        catalog_path: Path,
        settings_path: Path,
        data_directory: Path,
        *,
        key_id: str | None = None,
        key_secret: str | None = None,
        webhook_secret: str | None = None,
        mode: str | None = None,
        gateway: Any | None = None,
        security_store: SecurityStore | None = None,
        shop_workflow: ShopWorkflow | None = None,
        payment_test_enabled: bool | None = None,
        ordering_enabled: bool | None = None,
        payment_test_allowed_emails: set[str] | None = None,
        delivery_zone_store: DeliveryZoneStore | None = None,
    ) -> None:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        self._products_lock = threading.RLock()
        self._static_products = {item["id"]: item for item in catalog}
        self._dynamic_products: dict[str, dict[str, Any]] = {}
        self.products = dict(self._static_products)
        self._products_catalog_version: int | None = None
        self.settings = settings
        self.ordering_enabled = (
            ordering_enabled
            if ordering_enabled is not None
            else os.environ.get('STYLEDASH_ORDERING_ENABLED', 'false').strip().casefold() == 'true'
        )
        self.mode = (mode or os.environ.get("RAZORPAY_MODE", "test")).strip().lower()
        if self.mode not in ("test", "live"):
            raise RuntimeError("RAZORPAY_MODE must be test or live")
        prefix = f"RAZORPAY_{self.mode.upper()}"
        self.key_id = key_id if key_id is not None else os.environ.get(f"{prefix}_KEY_ID", "").strip()
        self.key_secret = key_secret if key_secret is not None else os.environ.get(f"{prefix}_KEY_SECRET", "").strip()
        self.webhook_secret = (
            webhook_secret
            if webhook_secret is not None
            else os.environ.get(f"{prefix}_WEBHOOK_SECRET", "").strip()
        )
        self.gateway = gateway
        if self.gateway is None and self.key_id and self.key_secret:
            self.gateway = RazorpayGateway(self.key_id, self.key_secret)
        self.store = JsonStateStore(data_directory / "orders.json")
        self.security = security_store
        self.shops = shop_workflow
        if self.shops is None and security_store is not None:
            self.shops = ShopWorkflow(security_store.path)
        self.refresh_shop_products()

        configured_pincodes = os.environ.get("STYLEDASH_SUPPORTED_PINCODES", "")
        if configured_pincodes.strip():
            self.supported_pincodes = {
                item.strip() for item in configured_pincodes.split(",") if item.strip()
            }
        else:
            self.supported_pincodes = set(settings["supportedPincodes"])

        self.delivery_zone_store = delivery_zone_store
        if self.delivery_zone_store is None and security_store is not None:
            self.delivery_zone_store = DeliveryZoneStore(security_store.path)
        delivery_zone_path = settings_path.parent / "delivery-zones.geojson"
        try:
            self.delivery_zone_fallback = (
                DeliveryZoneIndex.load(delivery_zone_path)
                if delivery_zone_path.exists()
                else DeliveryZoneIndex()
            )
        except DeliveryZoneConfigError as exc:
            raise RuntimeError("Invalid delivery-zone configuration.") from exc

        self.payment_test_enabled = (
            payment_test_enabled
            if payment_test_enabled is not None
            else os.environ.get("STYLEDASH_ENABLE_TEST_PRODUCT", "").strip().casefold() == "true"
        )
        if payment_test_allowed_emails is None:
            configured_emails = os.environ.get("STYLEDASH_TEST_PRODUCT_ALLOWED_EMAILS", "")
            candidates = {item.strip() for item in configured_emails.split(",") if item.strip()}
        else:
            candidates = payment_test_allowed_emails
        try:
            self.payment_test_allowed_emails = {normalize_email(item) for item in candidates}
        except SecurityError:
            raise RuntimeError("STYLEDASH_TEST_PRODUCT_ALLOWED_EMAILS contains an invalid email address") from None

    def health(self) -> dict[str, str]:
        result = {"status": "ok", "service": "Vibe4You"}
        if self.security is not None:
            result["database"] = "ok" if self.security.health() else "error"
        return result

    def refresh_shop_products(self) -> None:
        """Atomically refresh DB-backed products without rewriting catalog JSON.

        All shop submissions remain in the authoritative map. Non-published or
        suspended entries are retained with active=false so historic order
        inventory can still be finalized or released safely.

        The expensive full rebuild only runs when the catalogue version
        (bumped by DB triggers on every catalogue-affecting write, from any
        process) actually changed; otherwise the cached dynamic map is merged
        over the (small, in-memory) static catalogue again. This keeps static
        catalogue overrides effective while replacing a full product-table
        scan and JSON re-parse with a single-row counter read.
        """
        if self.shops is None:
            with self._products_lock:
                self.products = dict(self._static_products)
            return
        with self._products_lock:
            cached_version = self._products_catalog_version
            cached_dynamic = self._dynamic_products
        current_version = self.shops.catalog_version()
        if cached_version is not None and cached_version == current_version:
            snapshot = dict(self._static_products)
            snapshot.update(cached_dynamic)
            with self._products_lock:
                self.products = snapshot
            return
        dynamic = self.shops.payment_catalog_products()
        dynamic_map = {product["id"]: product for product in dynamic}
        snapshot = dict(self._static_products)
        snapshot.update(dynamic_map)
        with self._products_lock:
            self.products = snapshot
            self._dynamic_products = dynamic_map
            self._products_catalog_version = current_version

    def invalidate_shop_products(self) -> None:
        """Force the next refresh to rebuild (e.g. after local catalogue writes)."""
        with self._products_lock:
            self._products_catalog_version = None

    def product_snapshot(self) -> dict[str, dict[str, Any]]:
        with self._products_lock:
            return self.products

    @staticmethod
    def _public_delivery_request(request: dict[str, Any], *, admin: bool = False) -> dict[str, Any]:
        allowed = (
            "id", "productId", "productName", "productSlug", "variantId", "size",
            "colourName", "quantity", "unitPrice", "productSubtotal", "storeId",
            "storeName", "storeSlug", "address", "status", "quote", "createdAt",
            "updatedAt", "quotedAt", "paymentRequestedAt", "paidAt", "cancelledAt",
            "rejectedAt", "rejectionReason", "orderId", "razorpayOrderId",
            "razorpayPaymentId",
        )
        result = {key: request[key] for key in allowed if key in request}
        if admin:
            for key in ("userId", "quotedBy", "rejectedBy"):
                if key in request:
                    result[key] = request[key]
        return result

    def _validate_outstation_address(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ApiError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "Delivery address is required.",
                "invalid_delivery_request",
            )
        pincode = payload.get("pincode")
        if not _is_six_ascii_digits(pincode):
            raise ApiError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "Enter a valid 6-digit delivery pincode.",
                "invalid_delivery_request",
            )
        if pincode in self.supported_pincodes:
            raise ApiError(
                HTTPStatus.CONFLICT,
                "This address is in the Vibe4You direct delivery area. Use normal checkout instead.",
                "use_direct_checkout",
            )
        phone = _clean_string(payload.get("phone"), "phone number", 10, 16)
        if not all(character.isdigit() or character in "+ -" for character in phone):
            raise ApiError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "Invalid phone number.",
                "invalid_delivery_request",
            )
        return {
            "id": "addr-outstation",
            "name": _clean_string(payload.get("name"), "name", 2, 80),
            "phone": phone,
            "street": _clean_string(payload.get("street"), "street address", 5, 200),
            "city": _clean_string(payload.get("city"), "city", 2, 80),
            "state": _clean_string(payload.get("state"), "state", 2, 80),
            "pincode": pincode,
        }

    def create_delivery_request(self, user_id: str, payload: Any) -> dict[str, Any]:
        self.refresh_shop_products()
        products = self.product_snapshot()
        if not isinstance(payload, dict) or set(payload) - {"productId", "variantId", "quantity", "address"}:
            raise ApiError(
                HTTPStatus.BAD_REQUEST,
                "Invalid outside-delivery request.",
                "invalid_delivery_request",
            )
        product_id = payload.get("productId")
        variant_id = payload.get("variantId")
        quantity = payload.get("quantity")
        if not isinstance(product_id, str) or not isinstance(variant_id, str):
            raise ApiError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "Choose a valid product option.",
                "invalid_delivery_request",
            )
        product = products.get(product_id)
        if (
            not isinstance(product, dict)
            or product.get("active") is not True
            or product.get("outsideNeemuchDeliveryAvailable") is not True
        ):
            raise ApiError(
                HTTPStatus.CONFLICT,
                "This product is not available for delivery requests outside Neemuch.",
                "outside_delivery_unavailable",
            )
        variant = next(
            (
                candidate
                for candidate in product.get("variants", [])
                if candidate.get("id") == variant_id and candidate.get("active") is not False
            ),
            None,
        )
        if variant is None:
            raise ApiError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "Choose a valid product option.",
                "invalid_variant",
            )
        max_quantity = int(self.settings["maxQuantityPerItem"])
        if isinstance(quantity, bool) or not isinstance(quantity, int) or not 1 <= quantity <= max_quantity:
            raise ApiError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "Invalid item quantity.",
                "invalid_quantity",
            )
        address = self._validate_outstation_address(payload.get("address"))
        unit_price = _money(variant.get("price", product.get("price")), "price")
        subtotal = _rounded_rupees(unit_price * quantity)
        now = datetime.now(timezone.utc).isoformat()

        with self.store.lock:
            state = self.store.state
            if self._inventory(state, variant) < quantity:
                raise ApiError(
                    HTTPStatus.CONFLICT,
                    f"{product['name']} is no longer available in the requested quantity.",
                    "insufficient_stock",
                )
            active_statuses = {"requested", "quoted", "payment_pending"}
            for existing in state["deliveryRequests"].values():
                if (
                    isinstance(existing, dict)
                    and existing.get("userId") == user_id
                    and existing.get("productId") == product_id
                    and existing.get("variantId") == variant_id
                    and existing.get("quantity") == quantity
                    and existing.get("address") == address
                    and existing.get("status") in active_statuses
                ):
                    return {
                        "idempotent": True,
                        "request": self._public_delivery_request(existing),
                    }

            request_id = "delreq_" + secrets.token_hex(12)
            request = {
                "id": request_id,
                "userId": user_id[:128],
                "productId": product_id,
                "productName": product["name"],
                "productSlug": product["slug"],
                "variantId": variant["id"],
                "size": variant.get("size") or "One Size",
                "colourName": variant.get("colourName") or "",
                "quantity": quantity,
                "unitPrice": _rounded_rupees(unit_price),
                "productSubtotal": subtotal,
                "storeId": product.get("vendorId"),
                "storeName": product.get("storeName"),
                "storeSlug": product.get("storeSlug"),
                "address": address,
                "status": "requested",
                "createdAt": now,
                "updatedAt": now,
            }
            state["deliveryRequests"][request_id] = request
            self.store.save()
        return {"idempotent": False, "request": self._public_delivery_request(request)}

    def list_delivery_requests(self, user_id: str) -> list[dict[str, Any]]:
        with self.store.lock:
            rows = [
                self._public_delivery_request(request)
                for request in self.store.state["deliveryRequests"].values()
                if isinstance(request, dict) and request.get("userId") == user_id
            ]
        return sorted(rows, key=lambda item: item.get("updatedAt", ""), reverse=True)

    def admin_list_delivery_requests(self) -> list[dict[str, Any]]:
        with self.store.lock:
            rows = [
                self._public_delivery_request(request, admin=True)
                for request in self.store.state["deliveryRequests"].values()
                if isinstance(request, dict)
            ]
        return sorted(rows, key=lambda item: item.get("updatedAt", ""), reverse=True)

    def cancel_delivery_request(self, user_id: str, request_id: str) -> dict[str, Any]:
        with self.store.lock:
            request = self.store.state["deliveryRequests"].get(request_id)
            if not isinstance(request, dict) or request.get("userId") != user_id:
                raise ApiError(HTTPStatus.NOT_FOUND, "Delivery request not found.", "delivery_request_not_found")
            if request.get("status") not in {"requested", "quoted"}:
                raise ApiError(
                    HTTPStatus.CONFLICT,
                    "This delivery request can no longer be cancelled.",
                    "delivery_request_not_cancellable",
                )
            now = datetime.now(timezone.utc).isoformat()
            request.update({"status": "cancelled", "cancelledAt": now, "updatedAt": now})
            self.store.save()
            return self._public_delivery_request(request)

    def quote_delivery_request(
        self,
        request_id: str,
        delivery_fee_value: Any,
        note: Any,
        estimated_delivery: Any,
        admin_id: str,
    ) -> dict[str, Any]:
        try:
            fee = _money(delivery_fee_value, "delivery charge")
        except ApiError:
            raise
        if fee < Decimal("1") or fee > Decimal("10000"):
            raise ApiError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "Delivery charge must be between Rs 1 and Rs 10,000.",
                "invalid_delivery_quote",
            )
        clean_note = ""
        if note not in (None, ""):
            if not isinstance(note, str) or len(note.strip()) > 500:
                raise ApiError(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "Delivery note must be 500 characters or fewer.",
                    "invalid_delivery_quote",
                )
            clean_note = note.strip()
        clean_eta = ""
        if estimated_delivery not in (None, ""):
            if not isinstance(estimated_delivery, str):
                raise ApiError(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "Enter a valid delivery estimate.",
                    "invalid_delivery_quote",
                )
            clean_eta = estimated_delivery.strip()
            if not 1 <= len(clean_eta) <= 120:
                raise ApiError(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "Enter a valid delivery estimate.",
                    "invalid_delivery_quote",
                )
            if clean_eta.isdigit():
                days = int(clean_eta)
                if days < 1 or days > 90:
                    raise ApiError(
                        HTTPStatus.UNPROCESSABLE_ENTITY,
                        "Enter a delivery estimate between 1 and 90 days.",
                        "invalid_delivery_quote",
                    )
                clean_eta = f"{days} day" if days == 1 else f"{days} days"

        self.refresh_shop_products()
        products = self.product_snapshot()
        with self.store.lock:
            state = self.store.state
            request = state["deliveryRequests"].get(request_id)
            if not isinstance(request, dict):
                raise ApiError(HTTPStatus.NOT_FOUND, "Delivery request not found.", "delivery_request_not_found")
            if request.get("status") not in {"requested", "quoted"}:
                raise ApiError(
                    HTTPStatus.CONFLICT,
                    "This delivery request can no longer be quoted.",
                    "delivery_request_not_quotable",
                )
            product = products.get(request.get("productId"))
            if (
                not isinstance(product, dict)
                or product.get("active") is not True
                or product.get("outsideNeemuchDeliveryAvailable") is not True
            ):
                raise ApiError(
                    HTTPStatus.CONFLICT,
                    "The product is no longer available for outside-Neemuch delivery.",
                    "outside_delivery_unavailable",
                )
            variant = next(
                (
                    candidate
                    for candidate in product.get("variants", [])
                    if candidate.get("id") == request.get("variantId") and candidate.get("active") is not False
                ),
                None,
            )
            quantity = request.get("quantity")
            if variant is None or not isinstance(quantity, int) or self._inventory(state, variant) < quantity:
                raise ApiError(
                    HTTPStatus.CONFLICT,
                    "The requested product option is no longer in stock.",
                    "insufficient_stock",
                )
            unit_price = _money(variant.get("price", product.get("price")), "price")
            subtotal = _rounded_rupees(unit_price * quantity)
            delivery_fee = _rounded_rupees(fee)
            grand_total = subtotal + delivery_fee
            now = datetime.now(timezone.utc).isoformat()
            request.update({
                "productName": product["name"],
                "productSlug": product["slug"],
                "unitPrice": _rounded_rupees(unit_price),
                "productSubtotal": subtotal,
                "status": "quoted",
                "quote": {
                    "unitPrice": _rounded_rupees(unit_price),
                    "productSubtotal": subtotal,
                    "deliveryFee": delivery_fee,
                    "grandTotal": grand_total,
                    "note": clean_note,
                    "estimatedDelivery": clean_eta,
                },
                "quotedBy": admin_id,
                "quotedAt": now,
                "updatedAt": now,
            })
            self.store.save()
            return self._public_delivery_request(request, admin=True)

    def reject_delivery_request(self, request_id: str, reason: Any, admin_id: str) -> dict[str, Any]:
        if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 500:
            raise ApiError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "Enter a rejection reason between 3 and 500 characters.",
                "invalid_delivery_rejection",
            )
        with self.store.lock:
            request = self.store.state["deliveryRequests"].get(request_id)
            if not isinstance(request, dict):
                raise ApiError(HTTPStatus.NOT_FOUND, "Delivery request not found.", "delivery_request_not_found")
            if request.get("status") not in {"requested", "quoted"}:
                raise ApiError(
                    HTTPStatus.CONFLICT,
                    "This delivery request can no longer be rejected.",
                    "delivery_request_not_rejectable",
                )
            now = datetime.now(timezone.utc).isoformat()
            request.update({
                "status": "rejected",
                "rejectionReason": reason.strip(),
                "rejectedBy": admin_id,
                "rejectedAt": now,
                "updatedAt": now,
            })
            self.store.save()
            return self._public_delivery_request(request, admin=True)

    def create_delivery_request_order(
        self,
        user_id: str,
        request_id: str,
        payload: Any,
        idempotency_value: str | None,
    ) -> dict[str, Any]:
        self._require_ordering_enabled()
        if not isinstance(payload, dict) or set(payload) - {"paymentMethod"}:
            raise ApiError(
                HTTPStatus.BAD_REQUEST,
                "Invalid delivery payment request.",
                "invalid_delivery_payment",
            )
        payment_method = payload.get("paymentMethod")
        if payment_method not in ("upi", "card"):
            raise ApiError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "Outside-Neemuch delivery requests must be paid online.",
                "invalid_payment_method",
            )
        if not self.key_id or not self.key_secret or self.gateway is None:
            raise ApiError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "Online payments are temporarily unavailable.",
                "payments_not_configured",
            )
        if not self.key_id.startswith(f"rzp_{self.mode}_"):
            raise ApiError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "Payment configuration does not match the selected mode.",
                "payment_mode_mismatch",
            )
        idempotency_key = self._idempotency_key(idempotency_value)
        self.refresh_shop_products()
        products = self.product_snapshot()

        with self.store.lock:
            state = self.store.state
            request = state["deliveryRequests"].get(request_id)
            if not isinstance(request, dict) or request.get("userId") != user_id:
                raise ApiError(HTTPStatus.NOT_FOUND, "Delivery request not found.", "delivery_request_not_found")
            if request.get("status") == "paid":
                raise ApiError(HTTPStatus.CONFLICT, "This delivery request is already paid.", "delivery_request_paid")
            linked_order_id = request.get("orderId")
            if request.get("status") == "payment_pending" and isinstance(linked_order_id, str):
                existing = state["orders"].get(linked_order_id)
                if isinstance(existing, dict) and existing.get("razorpayOrderId"):
                    return self._create_response(existing)
            if request.get("status") != "quoted" or not isinstance(request.get("quote"), dict):
                raise ApiError(
                    HTTPStatus.CONFLICT,
                    "Wait for Vibe4You to confirm the delivery charge before paying.",
                    "delivery_quote_required",
                )
            if idempotency_key:
                stored_key = f"outside-delivery:{user_id}:{request_id}:{idempotency_key}"
                existing_id = state["idempotency"].get(stored_key)
                if existing_id:
                    existing = state["orders"].get(existing_id)
                    if isinstance(existing, dict) and existing.get("razorpayOrderId"):
                        return self._create_response(existing)
            else:
                stored_key = None

            product = products.get(request.get("productId"))
            if (
                not isinstance(product, dict)
                or product.get("active") is not True
                or product.get("outsideNeemuchDeliveryAvailable") is not True
            ):
                raise ApiError(
                    HTTPStatus.CONFLICT,
                    "The product is no longer available for outside-Neemuch delivery.",
                    "outside_delivery_unavailable",
                )
            variant = next(
                (
                    candidate
                    for candidate in product.get("variants", [])
                    if candidate.get("id") == request.get("variantId") and candidate.get("active") is not False
                ),
                None,
            )
            quantity = request.get("quantity")
            if variant is None or not isinstance(quantity, int) or self._inventory(state, variant) < quantity:
                raise ApiError(
                    HTTPStatus.CONFLICT,
                    "The requested product option is no longer in stock.",
                    "insufficient_stock",
                )
            current_unit = _rounded_rupees(_money(variant.get("price", product.get("price")), "price"))
            quote = request["quote"]
            if current_unit != quote.get("unitPrice"):
                now = datetime.now(timezone.utc).isoformat()
                request.update({"status": "requested", "updatedAt": now})
                request.pop("quote", None)
                request.pop("quotedAt", None)
                request.pop("quotedBy", None)
                self.store.save()
                raise ApiError(
                    HTTPStatus.CONFLICT,
                    "The product price changed. Vibe4You must confirm a fresh delivery quote before payment.",
                    "delivery_quote_stale",
                )

            trusted_item = {
                "productId": product["id"],
                "productName": product["name"],
                "productSlug": product["slug"],
                "variantId": variant["id"],
                "sku": variant["sku"],
                "size": variant.get("size") or "One Size",
                "colourName": variant.get("colourName") or "",
                "quantity": quantity,
                "unitPrice": quote["unitPrice"],
                "lineTotal": quote["productSubtotal"],
                "reservedVariantIds": [variant["id"]],
                "exchangeEligible": product.get("exchangeAvailable") is True,
            }
            for key, value in (
                ("storeId", product.get("vendorId")),
                ("storeName", product.get("storeName")),
                ("storeSlug", product.get("storeSlug")),
            ):
                if value:
                    trusted_item[key] = value
            images = variant.get("images") or product.get("images") or []
            image_url = product.get("thumbnail") or (images[0] if images else None)
            if image_url:
                trusted_item["imageUrl"] = image_url

            style_order_id = self._new_order_id()
            receipt = style_order_id
            amount_paise = int(quote["grandTotal"]) * 100
            gateway_order = self.gateway.create_order({
                "amount": amount_paise,
                "currency": self.settings["currency"],
                "receipt": receipt,
                "notes": {
                    "styleDashOrderId": style_order_id,
                    "deliveryRequestId": request_id,
                },
            })
            razorpay_order_id = gateway_order.get("id")
            if not isinstance(razorpay_order_id, str) or not razorpay_order_id.startswith("order_"):
                raise ApiError(
                    HTTPStatus.BAD_GATEWAY,
                    "Invalid response from payment service.",
                    "invalid_payment_response",
                )
            now = datetime.now(timezone.utc).isoformat()
            order = {
                "items": [trusted_item],
                "address": dict(request["address"]),
                "userId": user_id[:128],
                "deliveryMethod": "outstation",
                "couponCode": None,
                "subtotal": quote["productSubtotal"],
                "discount": 0,
                "walletAmount": 0,
                "deliveryFee": quote["deliveryFee"],
                "taxes": 0,
                "tryAtHomeFee": 0,
                "grandTotal": quote["grandTotal"],
                "amount": amount_paise,
                "currency": self.settings["currency"],
                "id": style_order_id,
                "receipt": receipt,
                "razorpayOrderId": razorpay_order_id,
                "paymentMethod": payment_method,
                "paymentStatus": "pending",
                "status": "payment_pending",
                "estimatedDelivery": quote.get("estimatedDelivery") or "Delivery timing will be confirmed by Vibe4You.",
                "statusHistory": [{
                    "status": "payment_pending",
                    "timestamp": now,
                    "note": f"Awaiting verified payment for delivery request {request_id}",
                }],
                "createdAt": now,
                "updatedAt": now,
                "deliveryRequestId": request_id,
                "adminLabels": ["Outside Neemuch delivery request"],
            }
            state["orders"][style_order_id] = order
            if stored_key:
                state["idempotency"][stored_key] = style_order_id
            request.update({
                "status": "payment_pending",
                "orderId": style_order_id,
                "razorpayOrderId": razorpay_order_id,
                "paymentRequestedAt": now,
                "updatedAt": now,
            })
            self.store.save()
            return self._create_response(order)

    def order_for_display(self, order: dict[str, Any]) -> dict[str, Any]:
        """Enrich safe order-item snapshots with current display-only metadata."""
        self.refresh_shop_products()
        products = self.product_snapshot()
        result = dict(order)
        # Supplier invoices are private financial records and must never be
        # exposed by customer-facing order APIs.
        result.pop("supplierBills", None)
        if "items" not in order:
            return result
        display_items: list[dict[str, Any]] = []
        for source in order.get("items", []) or []:
            item = dict(source)
            product = products.get(item.get("productId"))
            if product is not None:
                for key, product_key in (
                    ("storeId", "vendorId"), ("storeName", "storeName"),
                    ("storeSlug", "storeSlug"),
                ):
                    value = product.get(product_key)
                    if value and not item.get(key):
                        item[key] = value
                variant = next((candidate for candidate in product.get("variants", [])
                                if candidate.get("id") == item.get("variantId")), None)
                images = (variant or {}).get("images") or product.get("images") or []
                image_url = item.get("imageUrl") or product.get("thumbnail") or (images[0] if images else None)
                if image_url:
                    item["imageUrl"] = image_url
                if item.get("exchangeEligible") is True:
                    source_variant_id = item.get("variantId")
                    trial = item.get("tryAtHome")
                    if isinstance(trial, dict) and trial.get("status") == "selected":
                        source_variant_id = trial.get("keptVariantId") or source_variant_id
                    source_variant = next((candidate for candidate in product.get("variants", []) if candidate.get("id") == source_variant_id), None)
                    source_colour = (source_variant or {}).get("colourName") or item.get("colourName")
                    with self.store.lock:
                        available_variant_ids = {
                            candidate["id"] for candidate in product.get("variants", [])
                            if candidate.get("id") and self._inventory(self.store.state, candidate) > 0
                        }
                    item["exchangeOptions"] = [
                        {"variantId": candidate["id"], "size": candidate.get("size"), "colourName": candidate.get("colourName")}
                        for candidate in product.get("variants", [])
                        if candidate.get("active") is not False
                        and candidate.get("id") != source_variant_id
                        and candidate.get("colourName") == source_colour
                        and candidate.get("id") in available_variant_ids
                    ]
            display_items.append(item)
        result["items"] = display_items
        return result

    def receipt_pdf(self, order: dict[str, Any]) -> bytes:
        display = self.order_for_display(order)
        if display.get("status") != "delivered":
            raise SecurityError(409, "Receipt is available after delivery.", "receipt_not_ready")
        return build_receipt_pdf(
            display,
            registry_path=self.store.path.parent / "vibe4you-tax-classifications.sqlite3",
            service_policy_path=self.store.path.parent / "vibe4you-receipt-service-tax-policy.json",
        )

    @staticmethod
    def express_delivery_available(now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        india_time = current.astimezone(timezone(timedelta(hours=5, minutes=30)))
        return india_time.weekday() >= 5

    @staticmethod
    def product_express_eligible(product: dict[str, Any]) -> bool:
        # Express eligibility is site-wide on Saturday/Sunday. Per-product
        # deliveryType is retained only for backward-compatible catalogue data
        # and no longer gates checkout. Inactive products are still rejected
        # separately by calculate_order before this helper is consulted.
        return product.get("active") is not False

    @staticmethod
    def estimated_delivery_label(delivery_method: str) -> str:
        return "60 minutes" if delivery_method == "express" else "same day"

    def is_serviceable_pincode(self, pincode: str) -> bool:
        return _is_six_ascii_digits(pincode) and pincode in self.supported_pincodes

    def _delivery_zone_policy(self) -> DeliveryZoneIndex:
        if self.delivery_zone_store is not None:
            return self.delivery_zone_store.policy()
        return self.delivery_zone_fallback

    @staticmethod
    def _validate_coordinates(latitude: Any, longitude: Any) -> tuple[float | None, float | None]:
        if latitude is None and longitude is None:
            return None, None
        if latitude is None or longitude is None:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Both latitude and longitude are required.", "invalid_location")
        if (
            isinstance(latitude, bool) or not isinstance(latitude, (int, float))
            or isinstance(longitude, bool) or not isinstance(longitude, (int, float))
            or not math.isfinite(float(latitude)) or not math.isfinite(float(longitude))
            or not -90 <= float(latitude) <= 90
            or not -180 <= float(longitude) <= 180
        ):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Valid delivery coordinates are required.", "invalid_location")
        return float(latitude), float(longitude)

    def check_serviceability(
        self,
        pincode: Any,
        now: datetime | None = None,
        *,
        latitude: Any = None,
        longitude: Any = None,
    ) -> dict[str, Any]:
        if not _is_six_ascii_digits(pincode):
            raise ApiError(HTTPStatus.BAD_REQUEST, "A valid 6-digit pincode is required.", "invalid_pincode")
        latitude, longitude = self._validate_coordinates(latitude, longitude)
        policy = self._delivery_zone_policy()
        decision = policy.check(
            pincode, self.supported_pincodes, latitude=latitude, longitude=longitude
        )
        serviceable = decision.get("serviceable") is True
        if policy.mode == "pincode":
            if not serviceable:
                return {"success": True, "pincode": pincode, "serviceable": False}
            express_available = self.express_delivery_available(now)
            return {
                "success": True,
                "pincode": pincode,
                "serviceable": True,
                "city": "Neemuch",
                "state": "Madhya Pradesh",
                "expressAvailable": express_available,
                "estimatedDeliveryMinutes": 60 if express_available else None,
            }

        response: dict[str, Any] = {
            "success": True,
            "pincode": pincode,
            "serviceable": serviceable,
            "enforcementMode": "polygon",
            "locationRequired": decision.get("requiresLocation") is True,
        }
        if decision.get("reason"):
            response["reason"] = decision["reason"]
        if decision.get("zoneId"):
            response["zoneId"] = decision["zoneId"]
        if decision.get("zoneName"):
            response["zoneName"] = decision["zoneName"]
        if not serviceable:
            return response
        express_available = self.express_delivery_available(now)
        response.update({
            "city": "Neemuch",
            "state": "Madhya Pradesh",
            "expressAvailable": express_available,
            "estimatedDeliveryMinutes": 60 if express_available else None,
        })
        return response

    def can_access_payment_test_product(self, user: Any) -> bool:
        if (
            not self.payment_test_enabled
            or not isinstance(user, dict)
            or user.get("emailVerified") is not True
        ):
            return False
        try:
            normalized = normalize_email(user.get("email"))
        except SecurityError:
            return False
        return normalized in self.payment_test_allowed_emails

    def payment_test_product(self, user: Any) -> dict[str, Any]:
        if not self.can_access_payment_test_product(user):
            raise ApiError(HTTPStatus.NOT_FOUND, "Not found.", "not_found")
        return {
            "success": True,
            "product": {
                "id": PAYMENT_TEST_PRODUCT_ID,
                "slug": PAYMENT_TEST_PRODUCT_SLUG,
                "name": PAYMENT_TEST_PRODUCT_NAME,
                "price": PAYMENT_TEST_PRICE_RUPEES,
                "amount": PAYMENT_TEST_AMOUNT_PAISE,
                "currency": PAYMENT_TEST_CURRENCY,
                "fulfillmentRequired": False,
            },
        }

    def _inventory(self, state: dict[str, Any], variant: dict[str, Any]) -> int:
        return int(state["inventory"].get(variant["id"], variant["stock"]))

    def public_inventory_availability(self, variant_id: Any = None, product_ids: Any = None) -> dict[str, Any]:
        """Return only customer-safe, current availability for active catalog variants."""
        if variant_id is not None and (
            not isinstance(variant_id, str) or not variant_id or len(variant_id) > 128
        ):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid product option.", "invalid_variant")
        if product_ids is not None and (
            not isinstance(product_ids, list) or not product_ids or len(product_ids) > 32
            or any(not isinstance(product_id, str) or not product_id or len(product_id) > 128 for product_id in product_ids)
        ):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid product selection.", "invalid_product")
        if variant_id is not None and product_ids is not None:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Choose one inventory filter.", "invalid_inventory_filter")
        product_filter = set(product_ids) if product_ids is not None else None

        self.refresh_shop_products()
        products = self.product_snapshot()
        availability: list[dict[str, Any]] = []
        with self.store.lock:
            state = self.store.state
            for product in products.values():
                if not product.get("active") or (product_filter is not None and product["id"] not in product_filter):
                    continue
                for variant in product["variants"]:
                    if variant.get("active") is False:
                        continue
                    if variant_id is not None and variant["id"] != variant_id:
                        continue
                    availability.append({
                        "productId": product["id"],
                        "variantId": variant["id"],
                        "available": self._inventory(state, variant) > 0,
                    })
        return {"success": True, "availability": availability}

    def shop_inventory_snapshot(self, product_ids: list[str]) -> dict[str, int]:
        self.refresh_shop_products()
        products = self.product_snapshot()
        result: dict[str, int] = {}
        with self.store.lock:
            state = self.store.state
            for product_id in product_ids:
                product = products.get(product_id)
                if not product or not product.get("vendorId") or not product.get("variants"):
                    continue
                for variant in product["variants"]:
                    result[variant["id"]] = self._inventory(state, variant)
        return result

    def set_shop_inventory(
        self, product_id: str, stock: Any, variant_id: str | None = None
    ) -> dict[str, Any]:
        if (
            isinstance(stock, bool)
            or not isinstance(stock, int)
            or not 0 <= stock <= 100_000
        ):
            raise SecurityError(
                400,
                "Stock must be a whole number from 0 to 100000.",
                "invalid_inventory_adjustment",
            )
        self.refresh_shop_products()
        product = self.product_snapshot().get(product_id)
        if (
            not product
            or not product.get("vendorId")
            or not product.get("active")
            or not product.get("variants")
        ):
            raise SecurityError(
                409,
                "The published product is not currently active.",
                "published_product_required",
            )
        active_variants = [item for item in product["variants"] if item.get("active") is not False]
        if variant_id is None:
            if len(active_variants) != 1:
                raise SecurityError(
                    400,
                    "Choose the size whose stock you want to update.",
                    "variant_required",
                )
            variant = active_variants[0]
        else:
            variant = next(
                (item for item in active_variants if item["id"] == variant_id),
                None,
            )
            if variant is None:
                raise SecurityError(404, "Product size variant not found.", "variant_not_found")
        inventory_alert = None
        with self.store.lock:
            before = self._inventory(self.store.state, variant)
            inventory_alert = self._inventory_alert_for_change(
                product, variant, before, stock
            )
            self.store.state["inventory"][variant["id"]] = stock
            self.store.save()
        if inventory_alert is not None:
            _notify_inventory_alerts([inventory_alert])
        return {
            "productId": product_id,
            "variantId": variant["id"],
            "size": variant.get("size"),
            "before": before,
            "stock": stock,
        }

    def _validate_address(self, payload: dict[str, Any]) -> dict[str, Any]:
        address = payload.get("address")
        if not isinstance(address, dict):
            raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Delivery address is required.", "invalid_customer")
        pincode = address.get("pincode")
        if not _is_six_ascii_digits(pincode):
            raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Delivery is not available for this pincode.", "unsupported_pincode")
        try:
            serviceability = self.check_serviceability(
                pincode, latitude=address.get("latitude"), longitude=address.get("longitude")
            )
        except ApiError as exc:
            if exc.code == "invalid_location":
                raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, exc.message, exc.code) from None
            raise
        if not serviceability["serviceable"]:
            reason = serviceability.get("reason")
            if reason == "location_required":
                raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Confirm your delivery location before placing the order.", "delivery_location_required")
            if reason == "outside_delivery_zone":
                raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Delivery is not available at this location yet.", "outside_delivery_zone")
            raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Delivery is not available for this pincode.", "unsupported_pincode")
        phone = _clean_string(address.get("phone"), "phone number", 10, 16)
        if not all(character.isdigit() or character in "+ -" for character in phone):
            raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Invalid phone number.", "invalid_customer")
        trusted: dict[str, Any] = {
            "id": "addr-checkout",
            "name": _clean_string(address.get("name"), "name", 2, 80),
            "phone": phone,
            "street": _clean_string(address.get("street"), "street address", 5, 200),
            "city": _clean_string(address.get("city"), "city", 2, 80),
            "state": "Madhya Pradesh",
            "pincode": pincode,
        }
        if serviceability.get("enforcementMode") == "polygon":
            latitude, longitude = self._validate_coordinates(address.get("latitude"), address.get("longitude"))
            trusted.update({
                "latitude": latitude,
                "longitude": longitude,
                "deliveryZoneId": serviceability.get("zoneId"),
                "deliveryZoneName": serviceability.get("zoneName"),
            })
        return trusted

    def calculate_order(self, payload: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
        self.refresh_shop_products()
        products = self.product_snapshot()
        if not isinstance(payload, dict):
            raise ApiError(HTTPStatus.BAD_REQUEST, "A JSON object is required.", "malformed_request")
        items = payload.get("items")
        if not isinstance(items, list) or not items or len(items) > 50:
            raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "A non-empty cart is required.", "invalid_cart")

        delivery_method = payload.get("deliveryMethod")
        delivery_fees = self.settings["deliveryFees"]
        if delivery_method not in delivery_fees:
            raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Unsupported delivery method.", "invalid_delivery")
        if delivery_method == "express" and not self.express_delivery_available(now):
            raise ApiError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "Express Delivery is available Saturday and Sunday in Neemuch.",
                "express_delivery_unavailable",
            )

        wallet_amount = payload.get("walletAmount", 0)
        if wallet_amount not in (0, None):
            raise ApiError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "Wallet credit is unavailable until secure authentication is enabled.",
                "wallet_unavailable",
            )

        address = self._validate_address(payload)
        trusted_items: list[dict[str, Any]] = []
        subtotal = Decimal("0")
        try_at_home_fee = Decimal("0")
        seen_variants: set[str] = set()
        max_quantity = int(self.settings["maxQuantityPerItem"])

        with self.store.lock:
            state = self.store.state
            for item in items:
                if not isinstance(item, dict):
                    raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Invalid cart item.", "invalid_cart")
                product_id = item.get("productId")
                variant_id = item.get("variantId")
                quantity = item.get("quantity")
                if not isinstance(product_id, str) or product_id not in products:
                    raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "A product is unavailable.", "invalid_product")
                product = products[product_id]
                if not product.get("active"):
                    raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "A product is unavailable.", "invalid_product")
                if delivery_method == "express" and not self.product_express_eligible(product):
                    raise ApiError(
                        HTTPStatus.UNPROCESSABLE_ENTITY,
                        f"Express Delivery is unavailable because {product['name']} is not Express-eligible.",
                        "express_delivery_ineligible",
                    )
                variant = next(
                    (candidate for candidate in product["variants"] if candidate["id"] == variant_id),
                    None,
                )
                if variant is None or variant.get("active") is False:
                    raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "A product option is unavailable.", "invalid_variant")
                if isinstance(quantity, bool) or not isinstance(quantity, int) or not 1 <= quantity <= max_quantity:
                    raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Invalid item quantity.", "invalid_quantity")
                if variant_id in seen_variants:
                    raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Duplicate cart item.", "invalid_cart")
                try_variant_ids = item.get("tryAtHomeVariantIds")
                is_try_at_home = try_variant_ids is not None
                reserved_variant_ids = [variant_id]
                selected_variants = [variant]
                if is_try_at_home:
                    if product.get("tryAtHomeAvailable") is not True:
                        raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Try at Home is not available for this product.", "try_at_home_unavailable")
                    if quantity != 1 or item.get("tryAtHomeTermsAccepted") is not True:
                        raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Accept the Try at Home terms and select two sizes.", "try_at_home_terms_required")
                    if not isinstance(try_variant_ids, list) or len(try_variant_ids) != 2 or any(not isinstance(value, str) for value in try_variant_ids):
                        raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Choose exactly two distinct sizes for Try at Home.", "invalid_try_at_home_sizes")
                    if variant_id not in try_variant_ids or len(set(try_variant_ids)) != 2:
                        raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Choose exactly two distinct sizes for Try at Home.", "invalid_try_at_home_sizes")
                    selected_variants = [next((entry for entry in product["variants"] if entry["id"] == candidate_id and entry.get("active") is not False), None) for candidate_id in try_variant_ids]
                    if any(candidate is None for candidate in selected_variants):
                        raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "A selected Try at Home size is unavailable.", "invalid_try_at_home_sizes")
                    if selected_variants[0]["size"] == selected_variants[1]["size"] or selected_variants[0].get("colourName") != selected_variants[1].get("colourName"):
                        raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Choose two different sizes of the same colour.", "invalid_try_at_home_sizes")
                    if any(_money(candidate.get("price", product["price"]), "price") != _money(variant.get("price", product["price"]), "price") for candidate in selected_variants):
                        raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Try at Home requires both sizes to have the same final price.", "try_at_home_price_mismatch")
                    reserved_variant_ids = list(try_variant_ids)
                    try_at_home_fee += Decimal(TRY_AT_HOME_FEE_RUPEES)
                if any(candidate_id in seen_variants for candidate_id in reserved_variant_ids):
                    raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "A size can be reserved only once per order.", "invalid_cart")
                seen_variants.update(reserved_variant_ids)
                if any(self._inventory(state, candidate) < quantity for candidate in selected_variants):
                    raise ApiError(HTTPStatus.CONFLICT, f"A selected size of {product['name']} is no longer available.", "insufficient_stock")
                unit_price = _money(variant.get("price", product["price"]), "price")
                line_total = unit_price * quantity
                subtotal += line_total
                trusted_item = {
                        "productId": product_id,
                        "productName": product["name"],
                        "productSlug": product["slug"],
                        "variantId": variant["id"],
                        "sku": variant["sku"],
                        "size": variant["size"],
                        "colourName": variant["colourName"],
                        "quantity": quantity,
                        "unitPrice": _rounded_rupees(unit_price),
                        "lineTotal": _rounded_rupees(line_total),
                        "reservedVariantIds": reserved_variant_ids,
                        "exchangeEligible": product.get("exchangeAvailable") is True,
                    }
                if is_try_at_home:
                    trusted_item["tryAtHome"] = {
                        "originalVariantIds": list(reserved_variant_ids),
                        "selectedSizes": [candidate["size"] for candidate in selected_variants],
                        "selectedColour": selected_variants[0].get("colourName"),
                        "fee": TRY_AT_HOME_FEE_RUPEES,
                        "tryMinutes": TRY_AT_HOME_MINUTES,
                        "lateFee": TRY_AT_HOME_LATE_FEE_RUPEES,
                        "termsAccepted": True,
                        "status": "reserved",
                    }
                # GST rates and HSN come from the trusted approved registry;
                # never use seller-supplied listing metadata as approval.
                for key, value in (
                    ("storeId", product.get("vendorId")),
                    ("storeName", product.get("storeName")),
                    ("storeSlug", product.get("storeSlug")),
                ):
                    if value:
                        trusted_item[key] = value
                images = variant.get("images") or product.get("images") or []
                image_url = product.get("thumbnail") or (images[0] if images else None)
                if image_url:
                    trusted_item["imageUrl"] = image_url
                trusted_items.append(trusted_item)

        coupon_code = payload.get("couponCode")
        coupon_discount = Decimal("0")
        applied_coupon: str | None = None
        if coupon_code not in (None, ""):
            if not isinstance(coupon_code, str):
                raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Invalid coupon.", "invalid_coupon")
            normalized = coupon_code.strip().upper()
            coupon = next((entry for entry in self.settings["coupons"] if entry["code"] == normalized), None)
            if (
                coupon is None
                or not coupon.get("active")
                or date.fromisoformat(coupon["expiryDate"]) < date.today()
                or subtotal < _money(coupon["minOrderValue"], "coupon")
            ):
                raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "This coupon is not eligible.", "invalid_coupon")
            if coupon["discountType"] == "fixed":
                coupon_discount = _money(coupon["value"], "coupon")
            else:
                coupon_discount = subtotal * _money(coupon["value"], "coupon") / Decimal("100")
                if coupon.get("maxDiscount") is not None:
                    coupon_discount = min(coupon_discount, _money(coupon["maxDiscount"], "coupon"))
            coupon_discount = min(coupon_discount, subtotal)
            applied_coupon = normalized

        delivery_fee = _money(delivery_fees[delivery_method], "delivery fee")
        if delivery_method == "standard":
            free_delivery_threshold = _money(self.settings["freeDeliveryThreshold"], "free delivery threshold")
            if subtotal >= free_delivery_threshold:
                delivery_fee = Decimal("0")
        taxable_merchandise_total = max(Decimal("0"), subtotal - coupon_discount)
        gst_settings = self.settings.get("gst") if isinstance(self.settings.get("gst"), dict) else {}
        product_gst_enabled = gst_settings.get("productGstEnabled") is True

        # This deliberate policy switch keeps the newly-rebased generic GST
        # implementation below intact.  When no Phase 1 policy ID is set, it
        # behaves exactly as the current production source: product HSN/rate
        # wins, otherwise the configured default rate is used.  When this
        # narrow policy ID is set, however, *only* the twelve owner-approved
        # product identities may use the GST path.  That prevents enabling the
        # approved Casio classification from silently applying tax to any
        # other catalogue product through the generic default-rate fallback.
        phase1_active = (
            product_gst_enabled
            and gst_settings.get("phase1PolicyId") == GST_PHASE1_POLICY_ID
        )
        # A GST fee policy that has not been verified must not fabricate tax
        # data or block checkout: the entire basket falls back to pending.
        force_gst_snapshot_unavailable = False
        if phase1_active:
            if delivery_fee != 0 or try_at_home_fee != 0:
                force_gst_snapshot_unavailable = True
                phase1_active = False
            else:
                # Unverified Phase1 identity falls back to private-registry
                # check. The entire owner-approved Phase1 branch below is
                # unchanged for approved, fee-free baskets.
                try:
                    for _pending_gst_item in trusted_items:
                        classification_for_product(products[str(_pending_gst_item["productId"])])
                except GstPhase1ClassificationError:
                    phase1_active = False
        if phase1_active:
            if delivery_fee != 0 or try_at_home_fee != 0:
                raise ApiError(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "GST treatment for this delivery or service fee is pending review.",
                    "gst_fee_policy_pending",
                )
            for item in trusted_items:
                try:
                    classification = classification_for_product(
                        products[str(item["productId"])]
                    )
                except GstPhase1ClassificationError:
                    raise ApiError(
                        HTTPStatus.SERVICE_UNAVAILABLE,
                        "This product's GST classification is pending. Checkout is temporarily unavailable.",
                        "gst_classification_pending",
                    ) from None
                item.update(
                    {
                        "hsnCode": classification["hsnCode"],
                        "gstRate": classification["gstRate"],
                        "gstSupplyType": classification["supplyType"],
                        "gstEffectiveFrom": classification["effectiveFrom"],
                        "gstPolicyId": classification["policyId"],
                        "gstApprovalDate": classification["approvedOn"],
                    }
                )

            displayed_subtotal = _rounded_rupees(subtotal)
            displayed_discount = _rounded_rupees(coupon_discount)
            displayed_delivery_fee = _rounded_rupees(delivery_fee)
            displayed_try_at_home_fee = _rounded_rupees(try_at_home_fee)
            grand_total = taxable_merchandise_total + delivery_fee + try_at_home_fee
            displayed_grand_total = _rounded_rupees(grand_total)
            amount_paise = displayed_grand_total * 100
            if amount_paise < 100:
                raise ApiError(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "Order total is below the minimum amount.",
                    "invalid_amount",
                )

            taxes = Decimal("0")
            cgst_total = Decimal("0")
            sgst_total = Decimal("0")
            merchandise_gross = Decimal(
                displayed_grand_total - displayed_delivery_fee - displayed_try_at_home_fee
            )
            line_total_sum = sum(
                (Decimal(str(item["lineTotal"])) for item in trusted_items), Decimal("0")
            )
            allocated_gross = Decimal("0")
            for index, item in enumerate(trusted_items):
                if index == len(trusted_items) - 1:
                    gross = merchandise_gross - allocated_gross
                else:
                    gross = Decimal(
                        str(
                            _rounded_tax_rupees(
                                merchandise_gross
                                * Decimal(str(item["lineTotal"]))
                                / line_total_sum
                            )
                        )
                    )
                    allocated_gross += gross
                rate = _money(item["gstRate"], "GST rate") / Decimal("100")
                item_tax = gross * rate / (Decimal("1") + rate)
                tax = Decimal(str(_rounded_tax_rupees(item_tax)))
                cgst = Decimal(str(_rounded_tax_rupees(tax / Decimal("2"))))
                sgst = tax - cgst
                item.update(
                    {
                        "gstDiscountedGross": _rounded_tax_rupees(gross),
                        "taxableValue": _rounded_tax_rupees(gross - tax),
                        "gstAmount": float(tax),
                        "cgstAmount": float(cgst),
                        "sgstAmount": float(sgst),
                        "igstAmount": 0,
                        "taxType": "CGST_SGST",
                    }
                )
                taxes += tax
                cgst_total += cgst
                sgst_total += sgst
            taxes = Decimal(str(_rounded_tax_rupees(taxes)))
            if Decimal(amount_paise) / Decimal("100") != Decimal(displayed_grand_total):
                raise ApiError(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "The displayed order total could not be reconciled to the payment amount.",
                    "amount_reconciliation_failed",
                )
            return {
                "items": trusted_items,
                "address": address,
                "userId": str(payload.get("userId") or "guest-user-id")[:128],
                "deliveryMethod": delivery_method,
                "couponCode": applied_coupon,
                "subtotal": displayed_subtotal,
                "discount": displayed_discount,
                "walletAmount": 0,
                "deliveryFee": displayed_delivery_fee,
                "taxes": float(taxes),
                "tryAtHomeFee": displayed_try_at_home_fee,
                "grandTotal": displayed_grand_total,
                "amount": amount_paise,
                "currency": self.settings["currency"],
                "gstSnapshot": {
                    "policyId": GST_PHASE1_POLICY_ID,
                    "priceTreatment": "GST_INCLUSIVE",
                    "taxAlreadyIncludedInGrandTotal": True,
                    "ownerApprovalDate": GST_PHASE1_OWNER_APPROVAL_DATE,
                    "placeOfSupplyStateCode": "23",
                    "taxType": "CGST_SGST",
                    "includedTaxTotal": float(taxes),
                    "cgstTotal": float(cgst_total),
                    "sgstTotal": float(sgst_total),
                    "igstTotal": 0,
                },
            }

        # Keep the live v6 generic product-GST behaviour byte-for-byte in
        # logic: it is intentionally separate from the exact-ID policy above.
        tax_invoice_snapshot_status: str | None = "unavailable" if force_gst_snapshot_unavailable else None
        if product_gst_enabled and not force_gst_snapshot_unavailable:
            gst_registry=TaxClassificationRegistry(self.store.path.parent)
            approved_classifications: list[dict[str, str]] = []
            for item in trusted_items:
                classification=gst_registry.get(str(item["productId"]))
                if classification is None or classification["supply_type"] != "taxable":
                    approved_classifications = []
                    break
                approved_classifications.append(classification)
            if len(approved_classifications) == len(trusted_items):
                tax_invoice_snapshot_status = "complete"
                for item, classification in zip(trusted_items, approved_classifications):
                    item["hsnCode"]=classification["hsn_code"]
                    item["gstRate"]=classification["gst_rate"]
            else:
                # Product classification controls whether a GST invoice can be
                # generated; it must not control whether the customer can buy.
                # Keep the server-authoritative gross unchanged and omit the
                # entire basket's tax snapshot rather than publishing a partial
                # GST total or trusting supplier/catalogue tax metadata.
                tax_invoice_snapshot_status = "unavailable"
        default_tax_rate = Decimal("0")
        taxes = Decimal("0")
        discount_ratio = (coupon_discount / subtotal) if subtotal > 0 else Decimal("0")
        for item in trusted_items:
            configured_rate = item.get("gstRate")
            item_rate = default_tax_rate if configured_rate in (None, "") else (_money(configured_rate, "GST rate") / Decimal("100"))
            if not product_gst_enabled:
                item_rate = Decimal("0")
            discounted_line_total = Decimal(str(item["lineTotal"])) * (Decimal("1") - discount_ratio)
            item_tax = Decimal("0") if item_rate == 0 else discounted_line_total * item_rate / (Decimal("1") + item_rate)
            if tax_invoice_snapshot_status == "complete":
                item["taxableValue"] = _rounded_rupees(discounted_line_total - item_tax)
                item["gstAmount"] = _rounded_rupees(item_tax)
                # Retain fractional GST percentages; rounding to whole
                # percentages would corrupt frozen order tax classifications.
                item["gstRate"] = str(item_rate * Decimal("100"))
            taxes += item_tax
        taxes = Decimal(str(_rounded_rupees(taxes)))
        grand_total = taxable_merchandise_total + delivery_fee + try_at_home_fee
        amount_paise = _rounded_rupees(grand_total * Decimal("100"))
        if amount_paise < 100:
            raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Order total is below the minimum amount.", "invalid_amount")

        result = {
            "items": trusted_items,
            "address": address,
            "userId": str(payload.get("userId") or "guest-user-id")[:128],
            "deliveryMethod": delivery_method,
            "couponCode": applied_coupon,
            "subtotal": _rounded_rupees(subtotal),
            "discount": _rounded_rupees(coupon_discount),
            "walletAmount": 0,
            "deliveryFee": _rounded_rupees(delivery_fee),
            "taxes": _rounded_rupees(taxes),
            "tryAtHomeFee": _rounded_rupees(try_at_home_fee),
            "grandTotal": _rounded_rupees(grand_total),
            "amount": amount_paise,
            "currency": self.settings["currency"],
        }
        if tax_invoice_snapshot_status is not None:
            result["taxInvoiceSnapshotStatus"] = tax_invoice_snapshot_status
        return result

    def _new_order_id(self) -> str:
        return f"SD-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(3).upper()}"

    def _idempotency_key(self, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not 8 <= len(value) <= 128:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid idempotency key.", "invalid_idempotency_key")
        if not all(character.isalnum() or character in "-_" for character in value):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid idempotency key.", "invalid_idempotency_key")
        return value

    @staticmethod
    def _require_idempotency_owner(order: dict[str, Any], user_id: str) -> None:
        """Fail closed before an idempotent response can expose another order."""
        if str(order.get("userId") or "") != user_id:
            raise ApiError(
                HTTPStatus.CONFLICT,
                "This checkout retry key cannot be reused.",
                "idempotency_conflict",
            )

    def _public_order(self, order: dict[str, Any]) -> dict[str, Any]:
        display_order = self.order_for_display(order)
        allowed = (
            "id", "userId", "items", "address", "paymentMethod", "paymentStatus",
            "subtotal", "discount", "walletAmount", "deliveryFee", "taxes", "tryAtHomeFee", "grandTotal",
            "codAdvanceAmount", "codAdvancePaid", "codAdvancePaidAt", "codAmountDue", "codAmountCollected",
            "deliveryMethod", "estimatedDelivery", "status", "statusHistory", "createdAt",
            "updatedAt", "razorpayOrderId", "razorpayPaymentId", "paymentVerifiedAt",
            "paymentCollectionMethod", "paymentCollectedAt",
            "isPaymentTestOrder", "fulfillmentRequired", "adminLabels", "inventoryCommitted",
            "inventoryReleasedAt", "refundId", "refundAmount", "refundCurrency", "refundProcessedAt",
            "cancellationReason", "cancelledAt", "tryAtHomeLateFeeDue", "tryAtHomeLateFeePaid",
            "tryAtHomeLateFeeCollectionMethod", "tryAtHomeLateFeeCollectedAt",
            "deliveryRequestId", "gstSnapshot",
            "taxInvoiceSnapshotStatus",
        )
        public_order = {key: display_order[key] for key in allowed if key in display_order}
        cancellation = display_order.get("cancellationRequest")
        if isinstance(cancellation, dict):
            cancellation_allowed = (
                "status", "requestedAt", "feeDue", "feePaid", "feeCollectionMethod",
                "feeCollectedAt", "completedAt",
            )
            public_order["cancellationRequest"] = {
                key: cancellation[key] for key in cancellation_allowed if key in cancellation
            }
        exchanges = display_order.get("exchangeRequests")
        if isinstance(exchanges, list):
            exchange_allowed = (
                "id", "itemIndex", "productId", "sourceVariantId", "sourceSize",
                "targetVariantId", "targetSize", "colourName", "quantity", "status",
                "feeDue", "feePaid", "requestedAt", "approvedAt", "completedAt",
                "feeCollectionMethod", "feeCollectedAt", "updatedAt",
            )
            public_order["exchangeRequests"] = [
                {key: request[key] for key in exchange_allowed if key in request}
                for request in exchanges if isinstance(request, dict)
            ]
        return public_order

    def _create_response(self, order: dict[str, Any]) -> dict[str, Any]:
        return {
            "success": True,
            "styleDashOrderId": order["id"],
            "razorpayOrderId": order["razorpayOrderId"],
            "keyId": self.key_id,
            "amount": order["amount"],
            "currency": order["currency"],
            "receipt": order["receipt"],
            "trustedTotals": {
                "subtotal": order["subtotal"],
                "discount": order["discount"],
                "deliveryFee": order["deliveryFee"],
                "taxes": order["taxes"],
                **({"tryAtHomeFee": order["tryAtHomeFee"]} if order.get("tryAtHomeFee", 0) else {}),
                "grandTotal": order["grandTotal"],
                **({
                    "codAdvanceAmount": order["codAdvanceAmount"],
                    "codAmountDue": order["codAmountDue"],
                } if order.get("paymentMethod") == "cod" and "codAdvanceAmount" in order else {}),
            },
            **({
                "paymentDescription": f"Rs {order['codAdvanceAmount']} COD booking amount",
            } if order.get("paymentMethod") == "cod" and "codAdvanceAmount" in order else {}),
        }

    def _require_ordering_enabled(self) -> None:
        if not self.ordering_enabled:
            raise ApiError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                'Ordering is currently unavailable. Please try again shortly.',
                'ordering_temporarily_disabled',
            )

    def create_razorpay_order(self, payload: dict[str, Any], idempotency_value: str | None) -> dict[str, Any]:
        self._require_ordering_enabled()
        if not self.key_id or not self.key_secret or self.gateway is None:
            raise ApiError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "Online payments are temporarily unavailable.",
                "payments_not_configured",
            )
        expected_key_prefix = f"rzp_{self.mode}_"
        if not self.key_id.startswith(expected_key_prefix):
            raise ApiError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "Payment configuration does not match the selected mode.",
                "payment_mode_mismatch",
            )
        payment_method = payload.get("paymentMethod")
        if payment_method == "cod":
            # The Rs 50 COD booking advance is retired (2026-10-23). COD orders
            # are placed via /api/place-cod-order and paid in full on delivery.
            raise ApiError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "Cash on Delivery needs no online payment. Please refresh the page and place your COD order again.",
                "cod_no_online_payment",
            )
        if payment_method not in ("upi", "card", "cod"):
            raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "Unsupported online payment method.", "invalid_payment_method")
        idempotency_key = self._idempotency_key(idempotency_value)
        idempotency_scope = "cod-advance" if payment_method == "cod" else "online"
        request_user_id = str(payload.get("userId") or "guest-user-id")[:128]
        with self.store.lock:
            if idempotency_key:
                existing_id = self.store.state["idempotency"].get(f"{idempotency_scope}:{idempotency_key}")
                if existing_id:
                    existing = self.store.state["orders"].get(existing_id)
                    if existing:
                        self._require_idempotency_owner(existing, request_user_id)
                        if existing.get("razorpayOrderId"):
                            return self._create_response(existing)
            # Keep the idempotency check, gateway order creation and persistence
            # in one critical section so concurrent retries cannot create two
            # Razorpay orders for the same checkout attempt.
            calculated = self.calculate_order(payload)
            if payment_method == "cod" and calculated["grandTotal"] < COD_ADVANCE_RUPEES:
                raise ApiError(HTTPStatus.UNPROCESSABLE_ENTITY, "The COD booking amount exceeds this order total.", "cod_advance_exceeds_total")
            style_order_id = self._new_order_id()
            receipt = style_order_id
            payment_amount = COD_ADVANCE_PAISE if payment_method == "cod" else calculated["amount"]
            gateway_order = self.gateway.create_order(
                {
                    "amount": payment_amount,
                    "currency": calculated["currency"],
                    "receipt": receipt,
                    "notes": {
                        "styleDashOrderId": style_order_id,
                        **({"purpose": "cod_booking_advance", "codAdvanceRupees": str(COD_ADVANCE_RUPEES)} if payment_method == "cod" else {}),
                    },
                }
            )
            razorpay_order_id = gateway_order.get("id")
            if not isinstance(razorpay_order_id, str) or not razorpay_order_id.startswith("order_"):
                raise ApiError(HTTPStatus.BAD_GATEWAY, "Invalid response from payment service.", "invalid_payment_response")

            now = datetime.now(timezone.utc).isoformat()
            order = {
                **calculated,
                "id": style_order_id,
                "receipt": receipt,
                "razorpayOrderId": razorpay_order_id,
                "paymentMethod": payment_method,
                "paymentStatus": "pending",
                "status": "payment_pending",
                "estimatedDelivery": self.estimated_delivery_label(calculated["deliveryMethod"]),
                "statusHistory": [{"status": "payment_pending", "timestamp": now, "note": "Awaiting verified payment"}],
                "createdAt": now,
                "updatedAt": now,
            }
            if payment_method == "cod":
                order.update({
                    "amount": COD_ADVANCE_PAISE,
                    "codAdvanceAmount": COD_ADVANCE_RUPEES,
                    "codAdvancePaid": False,
                    "codAmountDue": calculated["grandTotal"] - COD_ADVANCE_RUPEES,
                    "statusHistory": [{"status": "payment_pending", "timestamp": now, "note": f"Awaiting verified Rs {COD_ADVANCE_RUPEES} COD booking payment"}],
                })
            self.store.state["orders"][style_order_id] = order
            if idempotency_key:
                self.store.state["idempotency"][f"{idempotency_scope}:{idempotency_key}"] = style_order_id
            self.store.save()
            return self._create_response(order)

    def create_payment_test_order(
        self,
        user: dict[str, Any],
        payload: dict[str, Any],
        idempotency_value: str | None,
    ) -> dict[str, Any]:
        """Create an owner-authorized, exact-value Razorpay validation order."""
        if not self.can_access_payment_test_product(user):
            raise ApiError(HTTPStatus.NOT_FOUND, "Not found.", "not_found")
        user_id = str(user.get("id") or "")[:128]
        if not user_id:
            raise ApiError(HTTPStatus.NOT_FOUND, "Not found.", "not_found")
        if set(payload) - {"paymentMethod"}:
            raise ApiError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "Unsupported payment-test field.",
                "invalid_payment_test_request",
            )
        payment_method = payload.get("paymentMethod")
        if payment_method not in ("upi", "card"):
            raise ApiError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "Razorpay is required for this validation item.",
                "invalid_payment_method",
            )
        if self.settings.get("currency") != PAYMENT_TEST_CURRENCY:
            raise ApiError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "The payment validation item is unavailable.",
                "payment_test_configuration_error",
            )
        if not self.key_id or not self.key_secret or self.gateway is None:
            raise ApiError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "Online payments are temporarily unavailable.",
                "payments_not_configured",
            )
        if not self.key_id.startswith(f"rzp_{self.mode}_"):
            raise ApiError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "Payment configuration does not match the selected mode.",
                "payment_mode_mismatch",
            )

        idempotency_key = self._idempotency_key(idempotency_value)
        stored_idempotency_key = (
            f"payment-test:{user_id}:{idempotency_key}" if idempotency_key else None
        )
        with self.store.lock:
            if stored_idempotency_key:
                existing_id = self.store.state["idempotency"].get(stored_idempotency_key)
                if existing_id:
                    existing = self.store.state["orders"].get(existing_id)
                    if existing and existing.get("isPaymentTestOrder") is True:
                        return self._create_response(existing)

            style_order_id = self._new_order_id()
            receipt = style_order_id
            gateway_order = self.gateway.create_order({
                "amount": PAYMENT_TEST_AMOUNT_PAISE,
                "currency": PAYMENT_TEST_CURRENCY,
                "receipt": receipt,
                "notes": {
                    "styleDashOrderId": style_order_id,
                    "purpose": "payment_validation",
                    "fulfillmentRequired": "false",
                },
            })
            razorpay_order_id = gateway_order.get("id")
            if not isinstance(razorpay_order_id, str) or not razorpay_order_id.startswith("order_"):
                raise ApiError(HTTPStatus.BAD_GATEWAY, "Invalid response from payment service.", "invalid_payment_response")

            now = datetime.now(timezone.utc).isoformat()
            order = {
                "id": style_order_id,
                "receipt": receipt,
                "razorpayOrderId": razorpay_order_id,
                "userId": user_id,
                "items": [{
                    "productId": PAYMENT_TEST_PRODUCT_ID,
                    "productName": PAYMENT_TEST_PRODUCT_NAME,
                    "productSlug": PAYMENT_TEST_PRODUCT_SLUG,
                    "variantId": PAYMENT_TEST_VARIANT_ID,
                    "sku": "PAYMENT-VALIDATION-ONLY",
                    "size": "N/A",
                    "colourName": "N/A",
                    "quantity": 1,
                    "unitPrice": PAYMENT_TEST_PRICE_RUPEES,
                    "lineTotal": PAYMENT_TEST_PRICE_RUPEES,
                }],
                "address": {
                    "id": "payment-test-no-fulfillment",
                    "name": "Payment validation only",
                    "phone": "",
                    "street": "No fulfillment required",
                    "city": "",
                    "state": "",
                    "pincode": "",
                },
                "paymentMethod": payment_method,
                "paymentStatus": "pending",
                "subtotal": PAYMENT_TEST_PRICE_RUPEES,
                "discount": 0,
                "walletAmount": 0,
                "deliveryFee": 0,
                "taxes": 0,
                "grandTotal": PAYMENT_TEST_PRICE_RUPEES,
                "amount": PAYMENT_TEST_AMOUNT_PAISE,
                "currency": PAYMENT_TEST_CURRENCY,
                "deliveryMethod": "none",
                "estimatedDelivery": "No fulfillment required",
                "status": "payment_pending",
                "statusHistory": [{
                    "status": "payment_pending",
                    "timestamp": now,
                    "note": "TEST payment awaiting captured-state verification; no fulfillment required",
                }],
                "isPaymentTestOrder": True,
                "fulfillmentRequired": False,
                "adminLabels": list(PAYMENT_TEST_ADMIN_LABELS),
                "inventoryCommitted": False,
                "createdAt": now,
                "updatedAt": now,
            }
            self.store.state["orders"][style_order_id] = order
            if stored_idempotency_key:
                self.store.state["idempotency"][stored_idempotency_key] = style_order_id
            self.store.save()
            return self._create_response(order)

    def _inventory_alert_for_change(
        self,
        product: dict[str, Any],
        variant: dict[str, Any],
        before: int,
        after: int,
    ) -> dict[str, Any] | None:
        """Return one alert only when stock crosses an important threshold."""

        kind: str | None = None

        if before > 0 and after == 0:
            kind = "out_of_stock"
        elif (
            before > LOW_STOCK_THRESHOLD
            and 0 < after <= LOW_STOCK_THRESHOLD
        ):
            kind = "low_stock"

        if kind is None:
            return None

        return {
            "kind": kind,
            "productId": product.get("id"),
            "productName": product.get("name"),
            "variantId": variant.get("id"),
            "size": variant.get("size"),
            "colour": (
                variant.get("colourName")
                or variant.get("colour")
                or "-"
            ),
            "remaining": after,
        }

    @staticmethod
    def _reserved_variant_ids(item: dict[str, Any]) -> list[str]:
        raw = item.get("reservedVariantIds")
        if isinstance(raw, list) and raw and all(isinstance(value, str) and value for value in raw):
            return list(dict.fromkeys(raw))
        variant_id = item.get("variantId")
        return [variant_id] if isinstance(variant_id, str) and variant_id else []

    def _try_decrement_inventory(
        self,
        state: dict[str, Any],
        items: list[dict[str, Any]],
        *,
        inventory_alerts: list[dict[str, Any]] | None = None,
    ) -> bool:
        """Commit all normal and Try-at-Home reserved inventory or none of it."""
        products = self.product_snapshot()
        checked: list[tuple[dict[str, Any], dict[str, Any], int, int]] = []
        requested: set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                return False
            product = products.get(item.get("productId"))
            if not isinstance(product, dict):
                return False
            try:
                quantity = int(item.get("quantity", 0))
            except (TypeError, ValueError):
                return False
            if quantity <= 0:
                return False
            variant_ids = self._reserved_variant_ids(item)
            if not variant_ids:
                return False
            for variant_id in variant_ids:
                if variant_id in requested:
                    return False
                requested.add(variant_id)
                variant = next((entry for entry in product.get("variants", []) if entry.get("id") == variant_id), None)
                if not isinstance(variant, dict):
                    return False
                remaining = self._inventory(state, variant)
                if remaining < quantity:
                    return False
                checked.append((product, variant, remaining, quantity))
        for product, variant, remaining, quantity in checked:
            after = remaining - quantity
            state["inventory"][variant["id"]] = after
            if inventory_alerts is not None:
                alert = self._inventory_alert_for_change(product, variant, remaining, after)
                if alert is not None:
                    inventory_alerts.append(alert)
        return True

    def _decrement_inventory(
        self,
        state: dict[str, Any],
        items: list[dict[str, Any]],
        *,
        inventory_alerts: list[dict[str, Any]] | None = None,
    ) -> None:
        if not self._try_decrement_inventory(
            state,
            items,
            inventory_alerts=inventory_alerts,
        ):
            raise ApiError(
                HTTPStatus.CONFLICT,
                "Stock changed while the order was being processed. Contact support before retrying.",
                "stock_changed",
            )

    def _release_inventory(
        self,
        state: dict[str, Any],
        order: dict[str, Any],
    ) -> bool:
        """Release committed inventory exactly once, including Try-at-Home reservations."""
        committed = order.get("inventoryCommitted")
        if committed is None:
            committed = order.get("paymentMethod") == "cod"
        if committed is not True:
            return False
        products = self.product_snapshot()
        restored: list[tuple[str, int, int]] = []
        seen: set[str] = set()
        for item in order.get("items", []):
            product = products.get(item.get("productId"))
            if not isinstance(product, dict):
                raise ApiError(HTTPStatus.CONFLICT, "Inventory could not be released safely.", "inventory_release_failed")
            try:
                quantity = int(item.get("quantity", 0))
            except (TypeError, ValueError):
                quantity = 0
            if quantity <= 0:
                raise ApiError(HTTPStatus.CONFLICT, "Inventory could not be released safely.", "inventory_release_failed")
            for variant_id in self._reserved_variant_ids(item):
                if variant_id in seen:
                    raise ApiError(HTTPStatus.CONFLICT, "Inventory could not be released safely.", "inventory_release_failed")
                seen.add(variant_id)
                variant = next((entry for entry in product.get("variants", []) if entry.get("id") == variant_id), None)
                if variant is None:
                    raise ApiError(HTTPStatus.CONFLICT, "Inventory could not be released safely.", "inventory_release_failed")
                restored.append((variant_id, self._inventory(state, variant), quantity))
        for variant_id, current, quantity in restored:
            state["inventory"][variant_id] = current + quantity
        order["inventoryCommitted"] = False
        order["inventoryReleasedAt"] = datetime.now(timezone.utc).isoformat()
        return True

    def finalize_try_at_home(self, order_id: str, user_id: str, item_index: int, kept_variant_id: str, now: datetime | None = None) -> dict[str, Any]:
        if isinstance(item_index, bool) or not isinstance(item_index, int) or item_index < 0:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Choose a valid Try at Home item.", "invalid_try_at_home_item")
        if not isinstance(kept_variant_id, str) or not kept_variant_id:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Choose the size you want to keep.", "invalid_try_at_home_size")
        current_time = now or datetime.now(timezone.utc)
        with self.store.lock:
            order = self.store.state["orders"].get(order_id)
            if order is None or order.get("userId") != user_id:
                raise ApiError(HTTPStatus.NOT_FOUND, "Order not found.", "order_not_found")
            if order.get("status") != "delivered":
                raise ApiError(HTTPStatus.CONFLICT, "Try at Home selection starts after delivery.", "try_at_home_not_started")
            items = order.get("items")
            if not isinstance(items, list) or item_index >= len(items):
                raise ApiError(HTTPStatus.BAD_REQUEST, "Choose a valid Try at Home item.", "invalid_try_at_home_item")
            item = items[item_index]
            trial = item.get("tryAtHome") if isinstance(item, dict) else None
            if not isinstance(trial, dict):
                raise ApiError(HTTPStatus.BAD_REQUEST, "This item does not use Try at Home.", "invalid_try_at_home_item")
            if trial.get("status") == "selected":
                if trial.get("keptVariantId") == kept_variant_id:
                    return self._public_order(order)
                raise ApiError(HTTPStatus.CONFLICT, "The kept size has already been confirmed.", "try_at_home_already_selected")
            reserved = self._reserved_variant_ids(item)
            if len(reserved) != 2 or kept_variant_id not in reserved:
                raise ApiError(HTTPStatus.BAD_REQUEST, "Choose one of the two delivered sizes.", "invalid_try_at_home_size")
            deadline_raw = trial.get("deadlineAt")
            if not isinstance(deadline_raw, str):
                raise ApiError(HTTPStatus.CONFLICT, "The Try at Home timer has not started.", "try_at_home_not_started")
            deadline = datetime.fromisoformat(deadline_raw.replace("Z", "+00:00"))
            product = self.product_snapshot().get(item.get("productId"))
            if not isinstance(product, dict):
                raise ApiError(HTTPStatus.CONFLICT, "Product data is unavailable for Try at Home.", "try_at_home_product_unavailable")
            kept = next((v for v in product.get("variants", []) if v.get("id") == kept_variant_id), None)
            rejected_id = next((value for value in reserved if value != kept_variant_id), None)
            rejected = next((v for v in product.get("variants", []) if v.get("id") == rejected_id), None)
            if kept is None or rejected is None or order.get("inventoryCommitted") is not True:
                raise ApiError(HTTPStatus.CONFLICT, "Reserved inventory is unavailable.", "try_at_home_inventory_unavailable")
            quantity = int(item.get("quantity", 0))
            if quantity <= 0:
                raise ApiError(HTTPStatus.CONFLICT, "Reserved inventory is invalid.", "try_at_home_inventory_unavailable")
            self.store.state["inventory"][rejected_id] = self._inventory(self.store.state, rejected) + quantity
            selected_at = current_time.isoformat()
            late = current_time > deadline
            item.update({"variantId": kept["id"], "sku": kept["sku"], "size": kept["size"], "colourName": kept["colourName"], "reservedVariantIds": [kept_variant_id]})
            trial.update({"status": "selected", "keptVariantId": kept_variant_id, "keptSize": kept["size"], "rejectedVariantId": rejected_id, "rejectedSize": rejected["size"], "selectedAt": selected_at, "lateFeeApplied": late})
            if late:
                order["tryAtHomeLateFeeDue"] = int(order.get("tryAtHomeLateFeeDue", 0) or 0) + TRY_AT_HOME_LATE_FEE_RUPEES
                order["tryAtHomeLateFeePaid"] = False
            order["updatedAt"] = selected_at
            note = f"Try at Home size confirmed: {kept['size']} kept; {rejected['size']} returned"
            if late:
                note += f"; â‚¹{TRY_AT_HOME_LATE_FEE_RUPEES} late fee due"
            order.setdefault("statusHistory", []).append({"status": "try_at_home_selected", "timestamp": selected_at, "note": note})
            self.store.save()
            return self._public_order(order)

    def request_customer_cancellation(self, order_id: str, user_id: str) -> dict[str, Any]:
        """Persist an owned cancellation request; Admin retains refund and inventory control."""
        allowed = {"payment_pending", "payment_review_required", "placed", "confirmed", "preparing", "packed", "out_for_delivery"}
        with self.store.lock:
            order = self.store.state["orders"].get(order_id)
            if not isinstance(order, dict) or order.get("userId") != user_id:
                raise ApiError(HTTPStatus.NOT_FOUND, "Order not found.", "order_not_found")
            if order.get("fulfillmentRequired") is False or order.get("status") not in allowed:
                raise ApiError(HTTPStatus.CONFLICT, "This order can no longer be cancelled.", "cancellation_unavailable")
            existing = order.get("cancellationRequest")
            if isinstance(existing, dict):
                return {"idempotent": True, "order": self._public_order(order)}
            now = datetime.now(timezone.utc).isoformat()
            fee_due = CANCELLATION_AFTER_DISPATCH_FEE_RUPEES if order.get("status") == "out_for_delivery" else 0
            order["cancellationRequest"] = {
                "status": "requested", "requestedAt": now, "feeDue": fee_due,
                "feePaid": fee_due == 0,
            }
            order["updatedAt"] = now
            note = "Customer cancellation requested"
            if fee_due:
                note += f"; Rs {fee_due} after-dispatch fee due"
            order.setdefault("statusHistory", []).append({"status": order.get("status"), "timestamp": now, "note": note})
            self.store.save()
            return {"idempotent": False, "order": self._public_order(order)}

    def initiate_full_refund_for_cancellation(
        self,
        order_id: str,
        requested_by: str,
        reason: Any,
    ) -> dict[str, Any]:
        """Submit one full Razorpay refund after an administrator approves cancellation."""
        if self.gateway is None or not hasattr(self.gateway, "create_refund"):
            raise ApiError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "Refund processing is not configured for the administrator service.",
                "refunds_not_configured",
            )
        if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 500:
            raise ApiError(
                HTTPStatus.BAD_REQUEST,
                "A cancellation reason is required.",
                "cancellation_reason_required",
            )
        cancellation_reason = " ".join(reason.strip().split())
        cancellable = {
            "payment_pending", "payment_review_required", "placed", "confirmed",
            "preparing", "packed", "out_for_delivery",
        }

        with self.store.lock:
            state = self.store.state
            order = state["orders"].get(order_id)
            if not isinstance(order, dict):
                raise ApiError(HTTPStatus.NOT_FOUND, "Order not found.", "order_not_found")
            if order.get("fulfillmentRequired") is False or order.get("status") not in cancellable:
                raise ApiError(
                    HTTPStatus.CONFLICT,
                    "This order can no longer be cancelled.",
                    "cancellation_unavailable",
                )
            refundable_cod_advance = (
                order.get("paymentMethod") == "cod"
                and order.get("codAdvancePaid") is True
                and order.get("status") not in {"packed", "out_for_delivery"}
            )
            if order.get("paymentMethod") not in ("upi", "card") and not refundable_cod_advance:
                raise ApiError(
                    HTTPStatus.CONFLICT,
                    "This order does not require an online-payment refund.",
                    "refund_not_applicable",
                )
            if order.get("paymentStatus") == "refunded":
                return {
                    "success": True,
                    "idempotent": True,
                    "pending": False,
                    "order": self._public_order(order),
                }
            if order.get("paymentStatus") != "paid" and not refundable_cod_advance:
                raise ApiError(
                    HTTPStatus.CONFLICT,
                    "Only a captured online payment can be refunded.",
                    "payment_not_refundable",
                )

            cancellation_request = order.get("cancellationRequest")
            if (
                order.get("status") == "out_for_delivery"
                and isinstance(cancellation_request, dict)
                and int(cancellation_request.get("feeDue", 0) or 0) > 0
                and cancellation_request.get("feePaid") is not True
            ):
                raise ApiError(
                    HTTPStatus.CONFLICT,
                    "Collect the Rs 50 after-dispatch cancellation fee before refunding.",
                    "cancellation_fee_required",
                )

            payment_id = order.get("razorpayPaymentId")
            if not isinstance(payment_id, str) or not payment_id:
                raise ApiError(
                    HTTPStatus.CONFLICT,
                    "The captured payment reference is unavailable.",
                    "payment_reference_missing",
                )
            amount = order.get("amount")
            currency = order.get("currency")
            if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
                raise ApiError(
                    HTTPStatus.CONFLICT,
                    "The captured payment amount is unavailable.",
                    "payment_amount_unavailable",
                )
            if not isinstance(currency, str) or not currency:
                raise ApiError(
                    HTTPStatus.CONFLICT,
                    "The captured payment currency is unavailable.",
                    "payment_currency_unavailable",
                )

            existing = order.get("refundRequest")
            if isinstance(existing, dict) and existing.get("status") in {
                "submitting", "submitted", "processing", "uncertain", "processed",
            }:
                return {
                    "success": True,
                    "idempotent": True,
                    "pending": existing.get("status") != "processed",
                    "order": self._public_order(order),
                }

            requested_at = datetime.now(timezone.utc).isoformat()
            request_token = "rfq_" + secrets.token_hex(12)
            order["refundRequest"] = {
                "status": "submitting",
                "requestedAt": requested_at,
                "requestedBy": str(requested_by)[:128],
                "amount": amount,
                "currency": currency,
                "reason": cancellation_reason,
                "requestToken": request_token,
                "cancelAfterRefund": True,
            }
            order["updatedAt"] = requested_at
            order.setdefault("statusHistory", []).append({
                "status": order.get("status"),
                "timestamp": requested_at,
                "note": "Administrator approved cancellation; full Razorpay refund submission started",
            })
            self.store.save()

        payload = {
            "amount": amount,
            "notes": {
                "styledash_order_id": order_id,
                "styledash_refund_token": request_token,
            },
        }
        try:
            refund = self.gateway.create_refund(payment_id, payload)
        except ApiError as error:
            failed_at = datetime.now(timezone.utc).isoformat()
            with self.store.lock:
                order = self.store.state["orders"].get(order_id)
                if isinstance(order, dict):
                    request = order.get("refundRequest")
                    if isinstance(request, dict) and request.get("requestToken") == request_token:
                        request["status"] = (
                            "failed"
                            if error.code in {"refund_rejected", "payment_auth_failed"}
                            else "uncertain"
                        )
                        request["failedAt"] = failed_at
                        request["errorCode"] = error.code
                        order["requiresAdminAttention"] = True
                        order["updatedAt"] = failed_at
                        order.setdefault("statusHistory", []).append({
                            "status": order.get("status"),
                            "timestamp": failed_at,
                            "note": (
                                "Razorpay refund request was rejected"
                                if request["status"] == "failed"
                                else "Razorpay refund request outcome is uncertain; verify before retrying"
                            ),
                        })
                        self.store.save()
            raise

        if not isinstance(refund, dict):
            refund = {}
        refund_id = refund.get("id")
        response_payment_id = refund.get("payment_id")
        response_amount = refund.get("amount")
        response_currency = refund.get("currency")
        invalid_response = (
            not isinstance(refund_id, str)
            or not refund_id
            or (response_payment_id is not None and response_payment_id != payment_id)
            or (response_amount is not None and response_amount != amount)
            or (response_currency is not None and response_currency != currency)
        )
        if invalid_response:
            uncertain_at = datetime.now(timezone.utc).isoformat()
            with self.store.lock:
                order = self.store.state["orders"].get(order_id)
                if isinstance(order, dict):
                    request = order.get("refundRequest")
                    if isinstance(request, dict) and request.get("requestToken") == request_token:
                        request.update({
                            "status": "uncertain",
                            "failedAt": uncertain_at,
                            "errorCode": "invalid_refund_response",
                        })
                        order["requiresAdminAttention"] = True
                        order["updatedAt"] = uncertain_at
                        self.store.save()
            raise ApiError(
                HTTPStatus.BAD_GATEWAY,
                "Razorpay returned an invalid refund response. Verify the payment in Razorpay before retrying.",
                "invalid_refund_response",
            )

        submitted_at = datetime.now(timezone.utc).isoformat()
        with self.store.lock:
            order = self.store.state["orders"].get(order_id)
            if not isinstance(order, dict):
                raise ApiError(HTTPStatus.NOT_FOUND, "Order not found.", "order_not_found")
            request = order.get("refundRequest")
            if isinstance(request, dict) and request.get("requestToken") == request_token:
                request.setdefault("razorpayRefundId", refund_id)
                request.setdefault("providerStatus", refund.get("status"))
                request.setdefault("submittedAt", submitted_at)
                if request.get("status") != "processed":
                    request["status"] = "submitted"
                order["updatedAt"] = submitted_at
                order.setdefault("statusHistory", []).append({
                    "status": order.get("status"),
                    "timestamp": submitted_at,
                    "note": f"Full Razorpay refund submitted ({refund_id}); awaiting signed refund.processed webhook",
                })
                self.store.save()
            return {
                "success": True,
                "idempotent": False,
                "pending": order.get("paymentStatus") != "refunded",
                "refundId": refund_id,
                "order": self._public_order(order),
            }

    def request_exchange(
        self, order_id: str, user_id: str, item_index: Any, target_variant_id: Any,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if isinstance(item_index, bool) or not isinstance(item_index, int) or item_index < 0:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Choose a valid order item.", "invalid_exchange_item")
        if not isinstance(target_variant_id, str) or not target_variant_id or len(target_variant_id) > 128:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Choose a replacement size.", "invalid_exchange_size")
        current_time = now or datetime.now(timezone.utc)
        self.refresh_shop_products()
        products = self.product_snapshot()
        with self.store.lock:
            order = self.store.state["orders"].get(order_id)
            if not isinstance(order, dict) or order.get("userId") != user_id:
                raise ApiError(HTTPStatus.NOT_FOUND, "Order not found.", "order_not_found")
            if order.get("status") != "delivered":
                raise ApiError(HTTPStatus.CONFLICT, "An exchange can be requested only after delivery.", "exchange_unavailable")
            delivered_at = next((entry.get("timestamp") for entry in reversed(order.get("statusHistory", [])) if entry.get("status") == "delivered"), order.get("updatedAt"))
            try:
                delivered_time = datetime.fromisoformat(str(delivered_at).replace("Z", "+00:00"))
            except (TypeError, ValueError):
                raise ApiError(HTTPStatus.CONFLICT, "Delivery time is unavailable. Contact support.", "exchange_unavailable") from None
            if current_time > delivered_time + timedelta(days=EXCHANGE_WINDOW_DAYS):
                raise ApiError(HTTPStatus.CONFLICT, "The exchange window has ended.", "exchange_window_closed")
            items = order.get("items")
            if not isinstance(items, list) or item_index >= len(items):
                raise ApiError(HTTPStatus.BAD_REQUEST, "Choose a valid order item.", "invalid_exchange_item")
            item = items[item_index]
            if not isinstance(item, dict) or item.get("exchangeEligible") is not True:
                raise ApiError(HTTPStatus.CONFLICT, "This product is not eligible for exchange.", "exchange_unavailable")
            trial = item.get("tryAtHome")
            if isinstance(trial, dict) and trial.get("status") != "selected":
                raise ApiError(HTTPStatus.CONFLICT, "Choose the kept Try at Home size before requesting an exchange.", "exchange_unavailable")
            source_variant_id = trial.get("keptVariantId") if isinstance(trial, dict) else item.get("variantId")
            product = products.get(item.get("productId"))
            if not isinstance(product, dict):
                raise ApiError(HTTPStatus.CONFLICT, "Product data is unavailable for exchange.", "exchange_unavailable")
            source = next((variant for variant in product.get("variants", []) if variant.get("id") == source_variant_id), None)
            target = next((variant for variant in product.get("variants", []) if variant.get("id") == target_variant_id and variant.get("active") is not False), None)
            if source is None or target is None or target_variant_id == source_variant_id or target.get("colourName") != source.get("colourName"):
                raise ApiError(HTTPStatus.BAD_REQUEST, "Choose another available size in the same colour.", "invalid_exchange_size")
            quantity = int(item.get("quantity", 0) or 0)
            if quantity <= 0:
                raise ApiError(HTTPStatus.CONFLICT, "The order item cannot be exchanged safely.", "exchange_unavailable")
            if self._inventory(self.store.state, target) < quantity:
                raise ApiError(HTTPStatus.CONFLICT, "The replacement size is no longer available.", "exchange_stock_changed")
            requests = order.setdefault("exchangeRequests", [])
            existing = next((entry for entry in requests if entry.get("itemIndex") == item_index and entry.get("status") in {"requested", "approved"}), None)
            if existing:
                if existing.get("targetVariantId") == target_variant_id:
                    return {"idempotent": True, "exchange": dict(existing), "order": self._public_order(order)}
                raise ApiError(HTTPStatus.CONFLICT, "An exchange request is already active for this item.", "exchange_already_requested")
            requested_at = current_time.isoformat()
            exchange = {
                "id": "exch_" + secrets.token_hex(10), "itemIndex": item_index,
                "productId": item.get("productId"), "sourceVariantId": source_variant_id,
                "sourceSize": source.get("size"), "targetVariantId": target_variant_id,
                "targetSize": target.get("size"), "colourName": target.get("colourName"),
                "quantity": quantity, "status": "requested",
                "feeDue": EXCHANGE_FEE_RUPEES, "feePaid": False,
                "requestedAt": requested_at, "inventoryAdjusted": False,
            }
            requests.append(exchange)
            order["updatedAt"] = requested_at
            order.setdefault("statusHistory", []).append({
                "status": "exchange_requested", "timestamp": requested_at,
                "note": f"Size exchange requested: {source.get('size')} to {target.get('size')}; Rs {EXCHANGE_FEE_RUPEES} fee due",
            })
            self.store.save()
            return {"idempotent": False, "exchange": dict(exchange), "order": self._public_order(order)}

    def _find_order_by_razorpay_id(self, razorpay_order_id: str) -> dict[str, Any] | None:
        return next(
            (
                order
                for order in self.store.state["orders"].values()
                if order.get("razorpayOrderId") == razorpay_order_id
            ),
            None,
        )

    def _find_order_by_payment_id(self, payment_id: str) -> dict[str, Any] | None:
        order_id = self.store.state["processedPayments"].get(payment_id)
        if order_id:
            order = self.store.state["orders"].get(order_id)
            if order is not None:
                return order
        return next(
            (
                order
                for order in self.store.state["orders"].values()
                if order.get("razorpayPaymentId") == payment_id
            ),
            None,
        )

    def _finalize_payment(
        self,
        style_order_id: str,
        razorpay_order_id: str,
        payment_id: str,
        *,
        source: str,
        amount: Any | None = None,
        currency: Any | None = None,
    ) -> dict[str, Any]:
        """Persist captured financial truth before fulfillment decisions."""

        inventory_alerts: list[dict[str, Any]] = []

        with self.store.lock:
            state = self.store.state
            order = state["orders"].get(style_order_id)
            if order is None:
                raise ApiError(HTTPStatus.NOT_FOUND, "Order not found.", "order_not_found")
            if order.get("razorpayOrderId") != razorpay_order_id:
                raise ApiError(HTTPStatus.BAD_REQUEST, "Payment does not match this order.", "order_mismatch")
            if amount is not None and (isinstance(amount, bool) or amount != order.get("amount")):
                raise ApiError(HTTPStatus.BAD_REQUEST, "Payment amount does not match this order.", "amount_mismatch")
            if currency is not None and currency != order.get("currency"):
                raise ApiError(HTTPStatus.BAD_REQUEST, "Payment currency does not match this order.", "currency_mismatch")

            processed_order_id = state["processedPayments"].get(payment_id)
            if processed_order_id and processed_order_id != style_order_id:
                raise ApiError(HTTPStatus.CONFLICT, "This payment is already associated with another order.", "duplicate_payment")
            cod_advance_order = order.get("paymentMethod") == "cod" and isinstance(order.get("codAdvanceAmount"), int)
            if order.get("paymentStatus") in ("paid", "refunded") or order.get("codAdvancePaid") is True:
                if order.get("razorpayPaymentId") == payment_id:
                    delivery_request_id = order.get("deliveryRequestId")
                    delivery_request = state["deliveryRequests"].get(delivery_request_id) if isinstance(delivery_request_id, str) else None
                    if isinstance(delivery_request, dict) and delivery_request.get("status") != "paid":
                        paid_at = order.get("paymentVerifiedAt") or datetime.now(timezone.utc).isoformat()
                        delivery_request.update({
                            "status": "paid",
                            "orderId": style_order_id,
                            "razorpayOrderId": razorpay_order_id,
                            "razorpayPaymentId": payment_id,
                            "paidAt": paid_at,
                            "updatedAt": paid_at,
                        })
                    if payment_id not in state["processedPayments"]:
                        state["processedPayments"][payment_id] = style_order_id
                    self.store.save()
                    return {"success": True, "idempotent": True, "duplicate": True, "order": self._public_order(order)}
                raise ApiError(HTTPStatus.CONFLICT, "This order already has a verified payment.", "duplicate_payment")

            payment_test_order = order.get("isPaymentTestOrder") is True
            if order.get("status") == "cancelled":
                # A capture can arrive after an administrator cancels a pending
                # Razorpay order. Preserve the financial fact, but never reopen
                # fulfillment or reserve inventory; this needs refund review.
                now = datetime.now(timezone.utc).isoformat()
                order.update({
                    "paymentStatus": "pending" if cod_advance_order else "paid",
                    "razorpayPaymentId": payment_id,
                    "paymentVerifiedAt": now,
                    "paymentVerificationSource": source,
                    "requiresAdminAttention": True,
                    "updatedAt": now,
                })
                if cod_advance_order:
                    order["codAdvancePaid"] = True
                    order["codAdvancePaidAt"] = now
                alert_id = f"captured_payment_after_cancellation:{style_order_id}:{payment_id}"
                state["operationalAlerts"].setdefault(alert_id, {
                    "id": alert_id,
                    "type": "captured_payment_after_cancellation",
                    "entityId": payment_id,
                    "razorpayPaymentId": payment_id,
                    "styleDashOrderId": style_order_id,
                    "status": "open",
                    "recordedAt": now,
                })
                order.setdefault("statusHistory", []).append({
                    "status": "cancelled",
                    "timestamp": now,
                    "note": "Razorpay capture received after cancellation; do not fulfill. Refund reconciliation required.",
                })
                state["processedPayments"][payment_id] = style_order_id
                self.store.save()
                return {
                    "success": True,
                    "idempotent": False,
                    "duplicate": False,
                    "order": self._public_order(order),
                }

            inventory_committed = False
            if not payment_test_order:
                inventory_committed = (
                    order.get("inventoryCommitted") is True
                    or self._try_decrement_inventory(
                        state,
                        order["items"],
                        inventory_alerts=inventory_alerts,
                    )
                )

            now = datetime.now(timezone.utc).isoformat()
            if payment_test_order:
                next_status = "payment_test_completed"
                note = f"TEST payment verified by {source}; no fulfillment required"
            elif cod_advance_order and inventory_committed:
                next_status = "placed"
                note = f"Rs {order['codAdvanceAmount']} COD booking payment verified by {source}; Rs {order['codAmountDue']} due at delivery"
            elif cod_advance_order:
                next_status = "payment_review_required"
                note = f"Rs {order['codAdvanceAmount']} COD booking payment verified by {source}; stock confirmation required; do not request another payment"
            elif inventory_committed:
                next_status = "placed"
                note = f"Razorpay payment verified by {source}"
            else:
                next_status = "payment_review_required"
                note = f"Razorpay payment verified by {source}; stock confirmation required; do not request another payment"

            order.update({
                "paymentStatus": "pending" if cod_advance_order else "paid",
                "status": next_status,
                "razorpayPaymentId": payment_id,
                "paymentVerifiedAt": now,
                "paymentVerificationSource": source,
                "inventoryCommitted": False if payment_test_order else inventory_committed,
                "updatedAt": now,
            })
            if cod_advance_order:
                order["codAdvancePaid"] = True
                order["codAdvancePaidAt"] = now
            if not payment_test_order and not inventory_committed:
                order["inventoryShortfall"] = True
                order["requiresAdminAttention"] = True
                alert_id = f"inventory_shortfall_after_capture:{style_order_id}"
                state["operationalAlerts"].setdefault(alert_id, {
                    "id": alert_id,
                    "type": "inventory_shortfall_after_capture",
                    "entityId": style_order_id,
                    "razorpayPaymentId": payment_id,
                    "styleDashOrderId": style_order_id,
                    "status": "open",
                    "recordedAt": now,
                })
            else:
                order.pop("inventoryShortfall", None)

            order.setdefault("statusHistory", []).append({"status": next_status, "timestamp": now, "note": note})
            state["processedPayments"][payment_id] = style_order_id
            delivery_request_id = order.get("deliveryRequestId")
            delivery_request = state["deliveryRequests"].get(delivery_request_id) if isinstance(delivery_request_id, str) else None
            if isinstance(delivery_request, dict):
                delivery_request.update({
                    "status": "paid",
                    "orderId": style_order_id,
                    "razorpayOrderId": razorpay_order_id,
                    "razorpayPaymentId": payment_id,
                    "paidAt": now,
                    "updatedAt": now,
                })
            self.store.save()
            public_order = self._public_order(order)

        # Financial state is already durable and the store lock has
        # been released. Duplicate finalizations return above and
        # therefore never reach this notification.
        _notify_finalized_payment(public_order)

        if inventory_alerts:
            _notify_inventory_alerts(inventory_alerts)

        return {
            "success": True,
            "idempotent": False,
            "duplicate": False,
            "order": public_order,
        }

    def verify_payment(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ApiError(HTTPStatus.BAD_REQUEST, "A JSON object is required.", "malformed_request")
        required = ("razorpay_order_id", "razorpay_payment_id", "razorpay_signature", "styleDashOrderId")
        if any(not isinstance(payload.get(field), str) or not payload[field].strip() for field in required):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Missing payment verification fields.", "missing_payment_fields")
        if not self.key_secret:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, "Payment verification is unavailable.", "payments_not_configured")

        style_order_id = payload["styleDashOrderId"]
        payment_id = payload["razorpay_payment_id"]
        with self.store.lock:
            order = self.store.state["orders"].get(style_order_id)
            if order is None:
                raise ApiError(HTTPStatus.NOT_FOUND, "Order not found.", "order_not_found")
            if order.get("razorpayOrderId") != payload["razorpay_order_id"]:
                raise ApiError(HTTPStatus.BAD_REQUEST, "Payment does not match this order.", "order_mismatch")
            expected = hmac.new(
                self.key_secret.encode("utf-8"),
                f"{order['razorpayOrderId']}|{payment_id}".encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(expected, payload["razorpay_signature"]):
                raise ApiError(HTTPStatus.BAD_REQUEST, "Payment verification failed.", "signature_mismatch")

            expected_amount = order["amount"]
            expected_currency = order["currency"]

        if self.gateway is None or not hasattr(self.gateway, "fetch_payment"):
            raise ApiError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "Payment capture verification is unavailable.",
                "payments_not_configured",
            )
        payment = self.gateway.fetch_payment(payment_id)
        if not isinstance(payment, dict):
            raise ApiError(HTTPStatus.BAD_GATEWAY, "Invalid response from payment service.", "invalid_payment_response")
        if payment.get("order_id") != payload["razorpay_order_id"]:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Payment does not match this order.", "order_mismatch")
        amount = payment.get("amount")
        currency = payment.get("currency")
        if isinstance(amount, bool) or amount != expected_amount:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Payment amount does not match this order.", "amount_mismatch")
        if currency != expected_currency:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Payment currency does not match this order.", "currency_mismatch")

        status = payment.get("status")
        if status == "authorized":
            return self._record_authorized_payment(style_order_id, payment_id)
        if status != "captured":
            raise ApiError(
                HTTPStatus.CONFLICT,
                "Payment has not been captured. The order remains pending.",
                "payment_not_captured",
            )
        return self._finalize_payment(
            style_order_id,
            payload["razorpay_order_id"],
            payment_id,
            source="browser callback",
            amount=amount,
            currency=currency,
        )

    def _record_authorized_payment(self, style_order_id: str, payment_id: str) -> dict[str, Any]:
        """Record authorization without treating it as captured or fulfilling inventory."""
        with self.store.lock:
            order = self.store.state["orders"].get(style_order_id)
            if order is None:
                raise ApiError(HTTPStatus.NOT_FOUND, "Order not found.", "order_not_found")
            if order.get("paymentStatus") == "paid" or order.get("codAdvancePaid") is True:
                return {"success": True, "pending": False, "idempotent": True, "order": self._public_order(order)}
            previous = order.get("lastAuthorizedPayment")
            if isinstance(previous, dict) and previous.get("razorpayPaymentId") == payment_id:
                return {"success": True, "pending": True, "idempotent": True, "order": self._public_order(order)}
            now = datetime.now(timezone.utc).isoformat()
            order["lastAuthorizedPayment"] = {"razorpayPaymentId": payment_id, "recordedAt": now}
            order["updatedAt"] = now
            self.store.save()
            return {"success": True, "pending": True, "idempotent": False, "order": self._public_order(order)}

    @staticmethod
    def _webhook_entity(payload: dict[str, Any], name: str) -> dict[str, Any]:
        container = payload.get("payload")
        wrapper = container.get(name) if isinstance(container, dict) else None
        entity = wrapper.get("entity") if isinstance(wrapper, dict) else None
        return entity if isinstance(entity, dict) else {}

    def _record_failed_payment(self, razorpay_order_id: str, payment_id: str | None) -> tuple[bool, bool, bool]:
        """Record every unique failure; alert once and escalate at five attempts."""
        with self.store.lock:
            order = self._find_order_by_razorpay_id(razorpay_order_id)
            if order is None or order.get("paymentStatus") == "paid" or order.get("codAdvancePaid") is True:
                return False, False, False
            previous = order.get("lastPaymentFailure")
            if isinstance(previous, dict) and payment_id and previous.get("razorpayPaymentId") == payment_id:
                return False, False, False
            failure_note = "Razorpay reported a failed payment attempt"
            prior_failures = sum(
                1 for entry in order.get("statusHistory", [])
                if isinstance(entry, dict) and entry.get("note") == failure_note
            )
            first_alert = previous is None and prior_failures == 0
            volume_alert = prior_failures == 4 and not order.get("paymentFailureVolumeAlertSentAt")
            now = datetime.now(timezone.utc).isoformat()
            # Existing orders with 5+ failures were already alerted by the old code.
            # Do not create another notification merely because this fix went live.
            if prior_failures >= 5 or volume_alert:
                order.setdefault("paymentFailureVolumeAlertSentAt", now)
            order["lastPaymentFailure"] = {
                "razorpayPaymentId": payment_id,
                "recordedAt": now,
            }
            order["updatedAt"] = now
            order["statusHistory"].append(
                {"status": "payment_pending", "timestamp": now, "note": failure_note}
            )
            self.store.save()
            return True, first_alert, volume_alert

    @staticmethod
    def _safe_webhook_event_id(event_id: str | None) -> str | None:
        if not isinstance(event_id, str):
            return None
        cleaned = event_id.strip()
        if not cleaned or len(cleaned) > 200 or any(ord(character) < 32 for character in cleaned):
            return None
        return cleaned

    def _record_operational_alert(
        self,
        event: str,
        entity_id: str,
        payment_id: str,
        razorpay_order_id: str | None,
        event_id: str | None,
    ) -> dict[str, Any]:
        """Persist a minimal private-admin alert without mutating fulfillment state."""
        alert_id = f"{event}:{entity_id}"
        safe_event_id = self._safe_webhook_event_id(event_id)
        with self.store.lock:
            state = self.store.state
            event_key = safe_event_id or alert_id
            previous_alert_id = state["processedWebhookEvents"].get(event_key)
            if previous_alert_id:
                return {"duplicate": True, "alert": state["operationalAlerts"].get(previous_alert_id)}
            existing = state["operationalAlerts"].get(alert_id)
            if existing is not None:
                state["processedWebhookEvents"][event_key] = alert_id
                self.store.save()
                return {"duplicate": True, "alert": existing}

            order = self._find_order_by_payment_id(payment_id)
            if order is None and razorpay_order_id:
                order = self._find_order_by_razorpay_id(razorpay_order_id)
            now = datetime.now(timezone.utc).isoformat()
            alert = {
                "id": alert_id,
                "type": event,
                "entityId": entity_id,
                "razorpayPaymentId": payment_id,
                "styleDashOrderId": order.get("id") if order else None,
                "status": "open",
                "recordedAt": now,
            }
            state["operationalAlerts"][alert_id] = alert
            state["processedWebhookEvents"][event_key] = alert_id
            if order is not None:
                order["requiresAdminAttention"] = True
                if event == "refund.failed":
                    order["refundFailureAttention"] = True
                    refund_request = order.get("refundRequest")
                    if isinstance(refund_request, dict):
                        known_refund_id = refund_request.get("razorpayRefundId")
                        if not known_refund_id or known_refund_id == entity_id:
                            refund_request.update({
                                "status": "failed",
                                "razorpayRefundId": entity_id,
                                "providerStatus": "failed",
                                "failedAt": now,
                                "errorCode": "refund_failed",
                            })
                elif event == "payment.dispute.created":
                    order["paymentDisputed"] = True
                    order["paymentDisputeId"] = entity_id
                order["updatedAt"] = now
            self.store.save()
            return {"duplicate": False, "alert": alert}

    def _record_refund_processed(
        self,
        refund: dict[str, Any],
        payment: dict[str, Any],
        event_id: str | None,
    ) -> dict[str, Any]:
        """Persist signed processed-refund truth without automatic restocking."""
        refund_id = refund.get("id")
        payment_id = refund.get("payment_id")
        amount = refund.get("amount")
        currency = refund.get("currency")
        if not isinstance(refund_id, str) or not refund_id:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Webhook is missing refund information.", "malformed_webhook")
        if not isinstance(payment_id, str) or not payment_id:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Webhook is missing payment information.", "malformed_webhook")
        if payment.get("id") and payment.get("id") != payment_id:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Webhook payment information does not match.", "malformed_webhook")
        if refund.get("status") != "processed":
            raise ApiError(HTTPStatus.BAD_REQUEST, "Webhook refund state is invalid.", "malformed_webhook")
        if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Webhook refund amount is invalid.", "malformed_webhook")
        if not isinstance(currency, str) or not currency:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Webhook refund currency is invalid.", "malformed_webhook")

        razorpay_order_id = payment.get("order_id") if isinstance(payment.get("order_id"), str) else None
        safe_event_id = self._safe_webhook_event_id(event_id)
        with self.store.lock:
            state = self.store.state
            existing = state["processedRefunds"].get(refund_id)
            if isinstance(existing, dict):
                order_id = existing.get("styleDashOrderId")
                order = state["orders"].get(order_id) if order_id else None
                return {"duplicate": True, "fullRefund": existing.get("fullRefund") is True, "order": self._public_order(order) if order else None}

            order = self._find_order_by_payment_id(payment_id)
            if order is None and razorpay_order_id:
                order = self._find_order_by_razorpay_id(razorpay_order_id)
            relation_matches = order is not None
            if order is not None:
                if order.get("razorpayPaymentId") and order.get("razorpayPaymentId") != payment_id:
                    relation_matches = False
                if razorpay_order_id and order.get("razorpayOrderId") and order.get("razorpayOrderId") != razorpay_order_id:
                    relation_matches = False
            payment_amount = payment.get("amount")
            payment_currency = payment.get("currency")
            cumulative_refunded = payment.get("amount_refunded")
            if isinstance(cumulative_refunded, bool) or not isinstance(
                cumulative_refunded,
                int,
            ):
                cumulative_refunded = None

            if order is not None:
                if (
                    payment_amount is not None
                    and (
                        isinstance(payment_amount, bool)
                        or not isinstance(payment_amount, int)
                        or payment_amount != order.get("amount")
                    )
                ):
                    relation_matches = False
                if (
                    payment_currency is not None
                    and payment_currency != order.get("currency")
                ):
                    relation_matches = False

            full_refund = bool(
                relation_matches
                and order is not None
                and currency == order.get("currency")
                and (
                    amount == order.get("amount")
                    or cumulative_refunded == order.get("amount")
                )
            )

            now = datetime.now(timezone.utc).isoformat()
            style_order_id = order.get("id") if order else None
            alert_type = "refund.processed" if full_refund else "refund.processed_review"
            alert_id = f"{alert_type}:{refund_id}"
            state["operationalAlerts"][alert_id] = {
                "id": alert_id,
                "type": alert_type,
                "entityId": refund_id,
                "razorpayPaymentId": payment_id,
                "styleDashOrderId": style_order_id,
                "status": "open",
                "recordedAt": now,
                "refundAmount": amount,
                "refundCurrency": currency,
            }
            state["processedRefunds"][refund_id] = {
                "styleDashOrderId": style_order_id,
                "razorpayPaymentId": payment_id,
                "amount": amount,
                "currency": currency,
                "fullRefund": full_refund,
                "recordedAt": now,
            }
            if safe_event_id:
                state["processedWebhookEvents"][safe_event_id] = alert_id
            auto_cancelled = False
            if order is not None:
                order["updatedAt"] = now
                if full_refund:
                    order["paymentStatus"] = "refunded"
                    order["razorpayPaymentId"] = payment_id
                    order["refundId"] = refund_id
                    # paymentStatus=refunded means the entire trusted order
                    # amount has been reconciled, even when several partial
                    # refunds made up that total.
                    order["refundAmount"] = order.get("amount")
                    order["refundCurrency"] = currency
                    order["refundProcessedAt"] = now
                    state["processedPayments"].setdefault(payment_id, order["id"])

                    refund_request = order.get("refundRequest")
                    if isinstance(refund_request, dict):
                        refund_request.update({
                            "status": "processed",
                            "razorpayRefundId": refund_id,
                            "providerStatus": "processed",
                            "processedAt": now,
                        })

                    should_cancel = (
                        isinstance(refund_request, dict)
                        and refund_request.get("cancelAfterRefund") is True
                        and order.get("status") != "cancelled"
                    )
                    if should_cancel:
                        try:
                            self._release_inventory(state, order)
                        except ApiError:
                            inventory_alert_id = f"refund_inventory_release_failed:{order['id']}"
                            state["operationalAlerts"][inventory_alert_id] = {
                                "id": inventory_alert_id,
                                "type": "refund_inventory_release_failed",
                                "entityId": order["id"],
                                "razorpayPaymentId": payment_id,
                                "styleDashOrderId": order["id"],
                                "status": "open",
                                "recordedAt": now,
                            }
                            order["requiresAdminAttention"] = True
                            note = (
                                "Razorpay confirmed a full refund; cancellation is held for "
                                "administrator inventory reconciliation"
                            )
                        else:
                            cancellation_reason = str(
                                refund_request.get("reason") or "Administrator approved cancellation"
                            )
                            order["status"] = "cancelled"
                            order["cancelledAt"] = now
                            order["cancellationReason"] = cancellation_reason
                            cancellation_request = order.get("cancellationRequest")
                            if isinstance(cancellation_request, dict):
                                cancellation_request.update({
                                    "status": "completed",
                                    "completedAt": now,
                                })
                            refund_request["cancellationCompletedAt"] = now
                            for pending_alert in state["operationalAlerts"].values():
                                if (
                                    isinstance(pending_alert, dict)
                                    and pending_alert.get("styleDashOrderId") == order["id"]
                                    and pending_alert.get("status") == "open"
                                    and pending_alert.get("type") in {
                                        "inventory_shortfall_after_capture",
                                        "refund.processed",
                                        "refund.processed_review",
                                    }
                                ):
                                    pending_alert.update({
                                        "status": "resolved",
                                        "resolvedAt": now,
                                        "resolution": "order_cancelled_after_admin_refund",
                                    })
                            order["requiresAdminAttention"] = any(
                                isinstance(pending_alert, dict)
                                and pending_alert.get("styleDashOrderId") == order["id"]
                                and pending_alert.get("status") == "open"
                                for pending_alert in state["operationalAlerts"].values()
                            )
                            auto_cancelled = True
                            note = "Razorpay confirmed a full refund; administrator-approved cancellation completed"
                    else:
                        order["requiresAdminAttention"] = True
                        note = "Razorpay confirmed a full refund; fulfillment state awaits administrator reconciliation"

                    order.setdefault("statusHistory", []).append({
                        "status": order.get("status", "payment_pending"),
                        "timestamp": now,
                        "note": note,
                    })
                else:
                    order["requiresAdminAttention"] = True
            self.store.save()
            return {
                "duplicate": False,
                "fullRefund": full_refund,
                "autoCancelled": auto_cancelled,
                "order": self._public_order(order) if order else None,
            }

    def process_webhook(
        self,
        raw_body: bytes,
        signature: str | None,
        event_id: str | None = None,
    ) -> dict[str, Any]:
        if not signature:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Missing webhook signature.", "missing_webhook_signature")
        if not self.webhook_secret:
            raise ApiError(HTTPStatus.UNAUTHORIZED, "Webhook verification failed.", "webhook_signature_mismatch")
        expected = hmac.new(self.webhook_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise ApiError(HTTPStatus.UNAUTHORIZED, "Webhook verification failed.", "webhook_signature_mismatch")
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Malformed JSON request.", "malformed_request") from None
        if not isinstance(payload, dict) or not isinstance(payload.get("event"), str):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Malformed webhook request.", "malformed_request")

        event = payload["event"]
        if event == "refund.processed":
            refund = self._webhook_entity(payload, "refund")
            payment = self._webhook_entity(payload, "payment")
            result = self._record_refund_processed(refund, payment, event_id)
            order = result.get("order") or {}
            print(
                f"Razorpay webhook event={event} styleOrderId={order.get('id') or '-'} "
                f"refundId={refund.get('id') or '-'} result={'duplicate' if result['duplicate'] else 'recorded'}",
                flush=True,
            )
            if not result["duplicate"]:
                refund_amount = refund.get("amount")
                amount_text = (
                    f"?{refund_amount / 100:.2f}"
                    if isinstance(refund_amount, int)
                    and not isinstance(refund_amount, bool)
                    else "-"
                )
                order_id = order.get("id") or "-"

                if result["fullRefund"]:
                    owner_notifier().send(
                        event="refund_processed",
                        title="Vibe4You Refund Processed",
                        message=(
                            f"Order: {order_id}\n"
                            f"Amount: {amount_text}\n"
                            f"Status: Refunded"
                        ),
                        priority=5,
                        tags=["money_with_wings"],
                    )
                else:
                    owner_notifier().send(
                        event="refund_review_required",
                        title="REFUND NEEDS ATTENTION",
                        message=(
                            f"Order: {order_id}\n"
                            f"Amount: {amount_text}\n"
                            f"Status: Review required"
                        ),
                        priority=5,
                        tags=["rotating_light"],
                    )

            response = {"success": True}
            if result["duplicate"]:
                response["duplicate"] = True
            if not result["fullRefund"]:
                response["reviewRequired"] = True
            return response
        if event == "payment.authorized":
            print("Razorpay webhook event=payment.authorized result=observed-not-fulfilled", flush=True)
            return {"success": True}
        if event in ("refund.failed", "payment.dispute.created"):
            entity_name = "refund" if event == "refund.failed" else "dispute"
            entity = self._webhook_entity(payload, entity_name)
            payment = self._webhook_entity(payload, "payment")
            entity_id = entity.get("id")
            payment_id = entity.get("payment_id") or payment.get("id")
            payment_entity_id = payment.get("id")
            if not isinstance(entity_id, str) or not entity_id:
                raise ApiError(HTTPStatus.BAD_REQUEST, "Webhook is missing alert information.", "malformed_webhook")
            if not isinstance(payment_id, str) or not payment_id:
                raise ApiError(HTTPStatus.BAD_REQUEST, "Webhook is missing payment information.", "malformed_webhook")
            if payment_entity_id and payment_entity_id != payment_id:
                raise ApiError(HTTPStatus.BAD_REQUEST, "Webhook payment information does not match.", "malformed_webhook")
            razorpay_order_id = payment.get("order_id")
            if not isinstance(razorpay_order_id, str):
                razorpay_order_id = None
            recorded = self._record_operational_alert(
                event, entity_id, payment_id, razorpay_order_id, event_id
            )
            alert = recorded["alert"] or {}
            print(
                f"Razorpay webhook event={event} styleOrderId={alert.get('styleDashOrderId') or '-'} "
                f"entityId={entity_id} result={'duplicate' if recorded['duplicate'] else 'alerted'}",
                flush=True,
            )
            if not recorded["duplicate"]:
                order_id = alert.get("styleDashOrderId") or "-"

                if event == "refund.failed":
                    owner_notifier().send(
                        event="refund_failed",
                        title="REFUND NEEDS ATTENTION",
                        message=(
                            f"Order: {order_id}\n"
                            f"Refund reference: ...{entity_id[-8:]}\n"
                            f"Status: Refund failed"
                        ),
                        priority=5,
                        tags=["rotating_light"],
                    )
                else:
                    owner_notifier().send(
                        event="payment_dispute",
                        title="PAYMENT DISPUTE ALERT",
                        message=(
                            f"Order: {order_id}\n"
                            f"Dispute reference: ...{entity_id[-8:]}\n"
                            f"Status: Immediate review required"
                        ),
                        priority=5,
                        tags=["rotating_light"],
                    )

            response = {"success": True}
            if recorded["duplicate"]:
                response["duplicate"] = True
            return response
        if event not in ("payment.captured", "payment.failed", "order.paid"):
            print(f"Razorpay webhook event={event} result=ignored", flush=True)
            return {"success": True}

        payment = self._webhook_entity(payload, "payment")
        order_entity = self._webhook_entity(payload, "order")
        payment_id = payment.get("id")
        razorpay_order_id = payment.get("order_id") or order_entity.get("id")
        if not isinstance(razorpay_order_id, str) or not razorpay_order_id:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Webhook is missing order information.", "malformed_webhook")

        with self.store.lock:
            style_order = self._find_order_by_razorpay_id(razorpay_order_id)
            style_order_id = style_order.get("id") if style_order else None
        if style_order_id is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "Order not found.", "order_not_found")

        if event == "payment.failed":
            recorded, first_failure_alert, volume_failure_alert = self._record_failed_payment(
                razorpay_order_id,
                payment_id if isinstance(payment_id, str) else None,
            )
            print(
                f"Razorpay webhook event={event} styleOrderId={style_order_id} "
                f"razorpayOrderId={razorpay_order_id} razorpayPaymentId={payment_id or '-'} "
                f"result={'failed' if recorded else 'ignored'}",
                flush=True,
            )

            if first_failure_alert:
                safe_payment_ref = (
                    f"...{payment_id[-8:]}"
                    if isinstance(payment_id, str) and payment_id
                    else "-"
                )

                owner_notifier().send(
                    event="payment_failed",
                    title="Vibe4You Payment Failed",
                    message=(
                        f"Order: {style_order_id}\n"
                        f"Payment reference: {safe_payment_ref}\n"
                        f"Status: Payment failed"
                    ),
                    priority=5,
                    tags=["warning"],
                )

            if volume_failure_alert:
                owner_notifier().send(
                    event="payment_failure_volume",
                    title="Vibe4You Repeated Failed Payment Attempts",
                    message=(
                        f"Order: {style_order_id}\n"
                        "Five failed payment attempts were recorded.\n"
                        "Review this order in the Razorpay dashboard."
                    ),
                    priority=5,
                    tags=["rotating_light"],
                )

            return {"success": True}

        if not isinstance(payment_id, str) or not payment_id:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Webhook is missing payment information.", "malformed_webhook")
        amount = payment.get("amount", order_entity.get("amount_paid", order_entity.get("amount")))
        currency = payment.get("currency", order_entity.get("currency"))
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Webhook is missing payment amount.", "malformed_webhook")
        if not isinstance(currency, str):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Webhook is missing payment currency.", "malformed_webhook")
        result = self._finalize_payment(
            style_order_id,
            razorpay_order_id,
            payment_id,
            source=f"{event} webhook",
            amount=amount,
            currency=currency,
        )
        print(
            f"Razorpay webhook event={event} styleOrderId={style_order_id} "
            f"razorpayOrderId={razorpay_order_id} razorpayPaymentId={payment_id} "
            f"result={'duplicate' if result['idempotent'] else 'processed'}",
            flush=True,
        )
        response = {"success": True}
        if result["idempotent"]:
            response["duplicate"] = True
        return response

    def place_cod_order(self, payload: dict[str, Any], idempotency_value: str | None) -> dict[str, Any]:
        self._require_ordering_enabled()
        idempotency_key = self._idempotency_key(idempotency_value)
        request_user_id = str(payload.get("userId") or "guest-user-id")[:128]
        inventory_alerts: list[dict[str, Any]] = []

        with self.store.lock:
            if idempotency_key:
                existing_id = self.store.state["idempotency"].get(
                    f"cod:{idempotency_key}"
                )
                if existing_id:
                    existing = self.store.state["orders"].get(
                        existing_id
                    )
                    if existing:
                        self._require_idempotency_owner(existing, request_user_id)
                        return {
                            "success": True,
                            "idempotent": True,
                            "order": self._public_order(existing),
                        }

            calculated = self.calculate_order(payload)
            now = datetime.now(timezone.utc).isoformat()
            style_order_id = self._new_order_id()

            order = {
                **calculated,
                "id": style_order_id,
                "paymentMethod": "cod",
                "paymentStatus": "pending",
                "status": "placed",
                "inventoryCommitted": True,
                "estimatedDelivery": self.estimated_delivery_label(calculated["deliveryMethod"]),
                "statusHistory": [{
                    "status": "placed",
                    "timestamp": now,
                    "note": "Cash on Delivery order placed",
                }],
                "createdAt": now,
                "updatedAt": now,
            }

            self._decrement_inventory(
                self.store.state,
                order["items"],
                inventory_alerts=inventory_alerts,
            )

            self.store.state["orders"][style_order_id] = order

            if idempotency_key:
                self.store.state["idempotency"][
                    f"cod:{idempotency_key}"
                ] = style_order_id

            self.store.save()
            public_order = self._public_order(order)

        # Inventory and order are both durable before notifying.
        if inventory_alerts:
            _notify_inventory_alerts(inventory_alerts)

        return {
            "success": True,
            "idempotent": False,
            "order": public_order,
        }


class StyleDashRequestHandler(SimpleHTTPRequestHandler):
    payment_service: PaymentService
    product_image_directory: Path
    review_workflow: ReviewWorkflow | None
    rate_limiter = RateLimiter()
    seo_store_lock = threading.Lock()
    seo_store_cache: dict[str, dict[str, Any]] = {}
    seo_store_expires = 0.0
    seo_store_failed = False

    def guess_type(self, path: str) -> str:
        content_type = super().guess_type(path)
        if "charset=" not in content_type and (
            content_type.startswith("text/")
            or content_type in {
                "application/javascript",
                "application/json",
                "application/xml",
                "image/svg+xml",
            }
        ):
            return f"{content_type}; charset=utf-8"
        return content_type

    def end_headers(self) -> None:
        path = urlsplit(self.path).path
        if path.startswith(("/assets/", "/media/product-images/")):
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        elif not path.startswith("/api/"):
            # HTML/navigation responses must never pin an old hashed bundle in
            # Android in-app browsers (notably Instagram WebView).
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        if self._is_canonical_public_host():
            self.send_header("Strict-Transport-Security", HSTS_POLICY)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Content-Security-Policy", SECURITY_POLICY)
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=(self)")
        # Local launch/deploy probes use this to prove which process owns 8080.
        # Never expose the runtime PID through the public hostname.
        if (self.headers.get("Host") or "").lower() in {"127.0.0.1:8080", "localhost:8080"}:
            self.send_header("X-StyleDash-Process-Id", str(os.getpid()))
        super().end_headers()

    def _json_response(
        self, status: int, payload: dict[str, Any], *, head_only: bool = False,
        headers: dict[str, str] | None = None,
    ) -> None:
        encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if not head_only:
            self.wfile.write(encoded)

    def _with_live_inventory(self, products: list[dict[str, Any]]) -> list[dict[str, Any]]:
        live_inventory = self.payment_service.shop_inventory_snapshot(
            [product["id"] for product in products]
        )
        for product in products:
            for variant in product.get("variants", []):
                stock = live_inventory.get(variant["id"])
                if stock is not None:
                    variant["stock"] = stock
        return products

    def _binary_response(self, status: int, body: bytes, content_type: str, headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for name, value in (headers or {}).items(): self.send_header(name, value)
        self.end_headers(); self.wfile.write(body)

    def _text_response(
        self, status: int, body: str, content_type: str, *, head_only: bool = False,
    ) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "public, max-age=300")
        self.end_headers()
        if not head_only:
            self.wfile.write(encoded)

    @staticmethod
    def _public_origin() -> str:
        return os.environ.get("STYLEDASH_PUBLIC_ORIGIN", "").rstrip("/")

    def _request_hostname(self) -> str | None:
        return urlsplit(f"//{self.headers.get('Host', '').strip()}").hostname

    def _is_canonical_public_host(self) -> bool:
        origin = self._public_origin()
        canonical_host = urlsplit(origin).hostname if origin else None
        request_host = self._request_hostname()
        return bool(
            canonical_host
            and request_host
            and request_host.lower() == canonical_host.lower()
        )

    def _trusted_forwarded_scheme(self) -> str | None:
        peer = self.client_address[0]
        trusted_proxy = (
            os.environ.get("STYLEDASH_TRUST_LOOPBACK_PROXY") == "1"
            and peer in ("127.0.0.1", "::1")
        )
        if not trusted_proxy:
            return None

        forwarded = self.headers.get("X-Forwarded-Proto", "").split(",", 1)[0].strip().lower()
        if forwarded in {"http", "https"}:
            return forwarded

        try:
            visitor = json.loads(self.headers.get("CF-Visitor", ""))
        except (TypeError, json.JSONDecodeError):
            return None
        scheme = visitor.get("scheme") if isinstance(visitor, dict) else None
        return scheme.lower() if isinstance(scheme, str) and scheme.lower() in {"http", "https"} else None

    def _redirect_http_to_https(self) -> bool:
        origin = self._public_origin()
        if (
            urlsplit(origin).scheme.lower() != "https"
            or not self._is_canonical_public_host()
            or self._trusted_forwarded_scheme() != "http"
        ):
            return False

        request_target = self.path if self.path.startswith("/") else f"/{self.path}"
        self.send_response(HTTPStatus.PERMANENT_REDIRECT)
        self.send_header("Location", f"{origin}{request_target}")
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.close_connection = True
        self.end_headers()
        return True

    def _product_image_file(self, request_path: str) -> tuple[Path, str] | None:
        match = PRODUCT_IMAGE_ROUTE_PATTERN.fullmatch(request_path)
        if match is None:
            return None
        filename = match.group(1)
        target = (self.product_image_directory / filename).resolve()
        if target.parent != self.product_image_directory.resolve():
            return None
        content_type = {"webp": "image/webp", "jpg": "image/jpeg", "png": "image/png"}[target.suffix.lstrip(".")]
        return target, content_type

    def _serve_product_image(self, request_path: str, *, head_only: bool = False) -> None:
        resolved = self._product_image_file(request_path)
        if resolved is None or not resolved[0].is_file():
            raise ApiError(HTTPStatus.NOT_FOUND, "Image not found.", "not_found")
        target, content_type = resolved
        body = b"" if head_only else target.read_bytes()
        size = target.stat().st_size
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(size))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def _store_product_image(self, payload: dict[str, Any]) -> dict[str, Any]:
        return store_product_image_payload(self.product_image_directory, payload)

    def _require_product_image_seller(self) -> dict[str, Any]:
        user, _session = self._current_user()
        self._csrf()
        application = self._shops().get_application(user["id"])
        if not application or application.get("status") not in {"APPROVED", "ACTIVE"}:
            raise SecurityError(403, "An approved shop is required before uploading product images.", "approved_shop_required")
        return user

    def _require_uploaded_store_branding(self, payload: Any) -> None:
        """Reject remote, malformed, or missing media before branding persistence."""
        if not isinstance(payload, dict):
            return
        for field in ("bannerImage", "logoImage"):
            value = payload.get(field)
            if value in (None, ""):
                continue
            if not isinstance(value, str):
                continue
            resolved = self._product_image_file(value)
            if resolved is None or not resolved[0].is_file():
                label = "store cover" if field == "bannerImage" else "store logo"
                raise SecurityError(
                    400,
                    f"Upload a valid {label} image.",
                    "invalid_store_branding",
                )

    def _redirect_to_canonical_host(self) -> bool:
        origin = self._public_origin()
        canonical_host = urlsplit(origin).hostname if origin else None
        request_host = self._request_hostname()
        if not canonical_host or not request_host:
            return False
        if request_host.lower() in {canonical_host.lower(), "localhost", "127.0.0.1", "::1"}:
            return False
        if urlsplit(self.path).path.startswith(API_PREFIX):
            return False

        request_target = self.path if self.path.startswith("/") else f"/{self.path}"
        self.send_response(HTTPStatus.PERMANENT_REDIRECT)
        self.send_header("Location", f"{origin}{request_target}")
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "public, max-age=300")
        self.end_headers()
        return True

    def _seo_origin(self) -> str:
        origin = self._public_origin()
        if origin:
            return origin
        if (self._request_hostname() or "").lower() in {"vibe4you.in", "www.vibe4you.in"}:
            return "https://vibe4you.in"
        return ""

    def _robots_body(self) -> str:
        origin = self._seo_origin()
        lines = ["User-agent: *", "Allow: /"]
        if origin:
            lines.append(f"Sitemap: {origin}/sitemap.xml")
        return "\n".join(lines) + "\n"

    def _sitemap_body(self) -> str:
        origin = self._seo_origin()
        if not origin:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, "Sitemap is unavailable.", "sitemap_unavailable")
        paths = [
            "/", "/products", "/categories", "/stores", "/help",
            "/returns", "/privacy", "/account-deletion", "/terms",
            *sorted(NEEMUCH_LOCAL_PAGES),
        ]
        product_paths = [
            f"/product/{product['slug']}"
            for product in self.payment_service.product_snapshot().values()
            if product.get("active") is True and isinstance(product.get("slug"), str)
        ]
        store_paths = [
            f"/store/{store['slug']}"
            for store in self._shops().list_active_stores()
            if isinstance(store.get("slug"), str) and store.get("slug")
        ]
        urls = paths + sorted(set(store_paths)) + sorted(set(product_paths))
        items = "".join(
            f"  <url><loc>{xml_escape(origin + path)}</loc></url>\n"
            for path in urls
        )
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{items}</urlset>\n"
        )

    def _neemuch_landing_body(self, path: str) -> str:
        page = NEEMUCH_LOCAL_PAGES.get(path)
        if page is None:
            raise ApiError(HTTPStatus.NOT_FOUND, "Not found.", "not_found")
        origin = self._seo_origin()
        if not origin:
            raise ApiError(HTTPStatus.SERVICE_UNAVAILABLE, "Page is unavailable.", "seo_origin_unavailable")

        products = self._shops().list_published_products()

        def normalized(value: Any) -> str:
            return str(value or "").strip().casefold()

        def matches(product: dict[str, Any]) -> bool:
            if product.get("active") is not True:
                return False
            if page.get("all_products") is True:
                return True
            product_category = normalized(product.get("category"))
            categories = tuple(normalized(value) for value in page.get("categories", ()))
            if categories:
                if product_category not in categories:
                    return False
            elif page.get("category") and product_category != normalized(page.get("category")):
                return False
            if page.get("department") and normalized(product.get("department")) != normalized(page.get("department")):
                return False
            subcategories = tuple(normalized(value) for value in page.get("subcategories", ()))
            terms = tuple(normalized(value) for value in page.get("terms", ()))
            if not subcategories and not terms:
                return True
            subcategory = normalized(product.get("subcategory"))
            name = normalized(product.get("name"))
            return subcategory in subcategories or any(term in name for term in terms)

        matching = [product for product in products if matches(product)]
        matching.sort(key=_homepage_sort_key, reverse=True)
        visible = matching[:36]

        directory_stores = None
        section_title = "Products available from local sellers"
        section_sub = f"Current Vibe4You listings relevant to {page['heading']}."
        count_label = "current local listings"
        if page.get("directory") == "stores":
            all_products = products
            counts: dict[str, int] = {}
            for listed in all_products:
                if listed.get("active") is True:
                    key = str(listed.get("storeName") or "").strip().casefold()
                    counts[key] = counts.get(key, 0) + 1
            directory_stores = [
                store for store in self._shops().list_active_stores()
                if isinstance(store.get("slug"), str) and store.get("slug")
            ]
            directory_stores.sort(
                key=lambda store: (
                    -counts.get(str(store.get("storeName") or "").strip().casefold(), 0),
                    str(store.get("storeName") or "").casefold(),
                )
            )
            matching = directory_stores
            visible = directory_stores
            section_title = "Local shops on Vibe4You"
            section_sub = "Every participating Neemuch store, with the number of products it currently lists."
            count_label = "local shops"

        def text(value: Any) -> str:
            return xml_escape(str(value or ""))

        def attr(value: Any) -> str:
            return xml_escape(str(value or ""), {'"': "&quot;", "'": "&#39;"})

        def absolute_url(value: str | None) -> str:
            raw = str(value or "").strip()
            if raw.startswith(("https://", "http://")):
                return raw
            if not raw:
                return ""
            return origin + (raw if raw.startswith("/") else "/" + raw)

        cards: list[str] = []
        for product in ([] if directory_stores is not None else visible):
            slug = str(product.get("slug") or "").strip()
            if not slug:
                continue
            name = str(product.get("name") or "Product")
            store_name = str(product.get("storeName") or "Local Neemuch store")
            image = absolute_url(product.get("thumbnail") or ((product.get("images") or [""])[0]))
            try:
                price_value = float(product.get("price"))
                price_text = f"{price_value:,.2f}".rstrip("0").rstrip(".")
            except (TypeError, ValueError):
                price_text = ""
            image_html = (
                f'<img src="{attr(image)}" alt="{attr(name)}" loading="lazy" decoding="async">'
                if image else '<div class="image-placeholder">Vibe4You</div>'
            )
            price_html = f'<div class="price">&#8377;{text(price_text)}</div>' if price_text else ""
            cards.append(
                f'<a class="product-card" href="{attr(origin + "/product/" + slug)}">'
                f'{image_html}<div class="product-copy">'
                f'<div class="store">{text(store_name)}</div>'
                f'<h3>{text(name)}</h3>{price_html}</div></a>'
            )

        if directory_stores is not None:
            for store in directory_stores:
                store_slug = str(store.get("slug") or "").strip()
                store_name = str(store.get("storeName") or "Local store")
                store_image = absolute_url(store.get("logoImage") or store.get("bannerImage"))
                store_count = counts.get(store_name.strip().casefold(), 0)
                store_blurb = " ".join(str(store.get("description") or "").split())[:110]
                store_image_html = (
                    f'<img src="{attr(store_image)}" alt="{attr(store_name)}" loading="lazy" decoding="async">'
                    if store_image else '<div class="image-placeholder">Vibe4You</div>'
                )
                count_html = (
                    f'<div class="price">{store_count} product{"s" if store_count != 1 else ""}</div>'
                    if store_count else ""
                )
                cards.append(
                    f'<a class="product-card" href="{attr(origin + "/store/" + store_slug)}">'
                    f'{store_image_html}<div class="product-copy">'
                    f'<div class="store">Neemuch</div>'
                    f'<h3>{text(store_name)}</h3><p class="sub">{text(store_blurb)}</p>{count_html}</div></a>'
                )

        related = "".join(
            f'<a href="{attr(origin + other_path)}">{text(other["heading"])}</a>'
            for other_path, other in NEEMUCH_LOCAL_PAGES.items()
            if other_path != path
        )
        search_variants = tuple(page.get("searches", ()))
        search_links = "".join(
            f'<a href="{attr(origin + href)}">{text(label)}</a>'
            for label, href in search_variants
        )
        item_list = [
            {
                "@type": "ListItem",
                "position": index + 1,
                "url": origin + ("/store/" if directory_stores is not None else "/product/") + str(product.get("slug") or ""),
                "name": str((product.get("storeName") if directory_stores is not None else product.get("name")) or ""),
            }
            for index, product in enumerate(visible[:(100 if directory_stores is not None else 24)])
            if product.get("slug")
        ]
        structured = {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "CollectionPage",
                    "@id": origin + path + "#page",
                    "url": origin + path,
                    "name": page["heading"],
                    "description": page["description"],
                    "alternateName": [label for label, _href in search_variants],
                    "about": {
                        "@type": "City",
                        "name": "Neemuch",
                        "address": {
                            "@type": "PostalAddress",
                            "addressLocality": "Neemuch",
                            "addressRegion": "Madhya Pradesh",
                            "addressCountry": "IN",
                        },
                    },
                    "isPartOf": {
                        "@type": "WebSite",
                        "@id": origin + "/#website",
                        "name": "Vibe4You",
                        "url": origin,
                    },
                },
                {
                    "@type": "BreadcrumbList",
                    "itemListElement": [
                        {"@type": "ListItem", "position": 1, "name": "Vibe4You", "item": origin + "/"},
                        {"@type": "ListItem", "position": 2, "name": page["heading"], "item": origin + path},
                    ],
                },
                {
                    "@type": "ItemList",
                    "name": page["heading"],
                    "numberOfItems": len(matching),
                    "itemListElement": item_list,
                },
            ],
        }
        structured_json = (
            json.dumps(structured, separators=(",", ":"), ensure_ascii=False)
            .replace("&", "\\u0026")
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
        )
        canonical = origin + path
        catalogue = origin + str(page.get("catalogue") or "/products")
        product_cards = "".join(cards) or '<p class="empty">New local products are being added. Browse the full Vibe4You catalogue for more options.</p>'
        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{text(page["title"])}</title>
<meta name="description" content="{attr(page["description"])}">
<meta name="robots" content="index,follow,max-image-preview:large">
<link rel="canonical" href="{attr(canonical)}">
<meta property="og:type" content="website">
<meta property="og:title" content="{attr(page["title"])}">
<meta property="og:description" content="{attr(page["description"])}">
<meta property="og:url" content="{attr(canonical)}">
<meta name="twitter:card" content="summary">
<link rel="icon" href="/favicon.svg">
<script type="application/ld+json">{structured_json}</script>
<style>
:root{{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#171717;background:#f7f7f7}}*{{box-sizing:border-box}}body{{margin:0}}a{{color:inherit;text-decoration:none}}.top{{background:#111;color:#fff}}.nav{{max-width:1180px;margin:auto;padding:16px 20px;display:flex;align-items:center;justify-content:space-between;gap:16px}}.brand{{font-size:22px;font-weight:900}}.brand b{{color:#b7f34a}}.navlinks{{display:flex;gap:16px;font-size:13px;font-weight:700}}.hero{{max-width:1180px;margin:auto;padding:54px 20px 58px}}.eyebrow{{display:inline-block;background:#b7f34a;color:#111;border-radius:999px;padding:7px 11px;font-size:12px;font-weight:900;text-transform:uppercase;letter-spacing:.04em}}h1{{font-size:clamp(34px,6vw,62px);line-height:1.02;margin:18px 0 14px;max-width:850px}}.intro{{font-size:17px;line-height:1.65;color:#d5d5d5;max-width:780px}}.stats{{margin-top:22px;display:flex;flex-wrap:wrap;gap:10px}}.pill{{border:1px solid #444;border-radius:12px;padding:9px 12px;font-size:13px;font-weight:700}}main{{max-width:1180px;margin:auto;padding:38px 20px 64px}}.section-head{{display:flex;align-items:end;justify-content:space-between;gap:20px;margin-bottom:22px}}h2{{font-size:28px;margin:0 0 6px}}.sub{{color:#666;margin:0;font-size:14px}}.cta{{background:#111;color:#fff;padding:12px 16px;border-radius:12px;font-weight:800;font-size:13px}}.grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:18px}}.product-card{{background:#fff;border:1px solid #e5e5e5;border-radius:18px;overflow:hidden;display:block;transition:.18s transform,.18s box-shadow}}.product-card:hover{{transform:translateY(-2px);box-shadow:0 10px 30px rgba(0,0,0,.08)}}.product-card img,.image-placeholder{{width:100%;aspect-ratio:4/5;object-fit:contain;background:#f2f2f2;padding:10px}}.image-placeholder{{display:flex;align-items:center;justify-content:center;font-weight:900;color:#777}}.product-copy{{padding:14px}}.store{{font-size:11px;color:#6b6b6b;font-weight:800;text-transform:uppercase;letter-spacing:.04em}}h3{{font-size:14px;line-height:1.35;margin:6px 0 10px}}.price{{font-weight:900;font-size:17px}}.searches{{margin-top:34px}}.search-links{{display:flex;flex-wrap:wrap;gap:9px}}.search-links a{{background:#efffcf;border:1px solid #b9e66a;border-radius:999px;padding:9px 13px;font-size:12px;font-weight:800}}.why{{margin-top:42px;background:#fff;border:1px solid #e5e5e5;border-radius:22px;padding:26px;display:grid;grid-template-columns:repeat(3,1fr);gap:22px}}.why h3{{font-size:16px}}.why p{{color:#626262;line-height:1.55;font-size:14px}}.more{{margin-top:34px}}.more-links{{display:flex;flex-wrap:wrap;gap:9px}}.more-links a{{background:#fff;border:1px solid #dedede;border-radius:999px;padding:9px 13px;font-size:12px;font-weight:800}}footer{{border-top:1px solid #ddd;padding:28px 20px;text-align:center;color:#666;font-size:12px}}@media(max-width:900px){{.grid{{grid-template-columns:repeat(3,1fr)}}}}@media(max-width:650px){{.navlinks{{display:none}}.hero{{padding-top:38px}}.grid{{grid-template-columns:repeat(2,1fr);gap:12px}}.section-head{{align-items:start;flex-direction:column}}.why{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<header class="top">
<nav class="nav"><a class="brand" href="{attr(origin)}/">Vibe<b>4You</b></a><div class="navlinks"><a href="{attr(origin)}/products">Products</a><a href="{attr(origin)}/stores">Local Stores</a><a href="{attr(origin)}/categories">Categories</a></div></nav>
<div class="hero"><div class="eyebrow">Shop Local in Neemuch</div><h1>{text(page["heading"])}</h1><p class="intro">{text(page["intro"])}</p><div class="stats"><span class="pill">{len(matching)} {text(count_label)}</span><span class="pill">Same Day Delivery in supported areas</span><span class="pill">Products from Neemuch stores</span></div></div>
</header>
<main>
<section><div class="section-head"><div><h2>{text(section_title)}</h2><p class="sub">{text(section_sub)}</p></div><a class="cta" href="{attr(catalogue)}">Open full catalogue</a></div><div class="grid">{product_cards}</div></section>
{f'<section class="searches"><h2>Related searches</h2><div class="search-links">{search_links}</div></section>' if search_links else ''}
<section class="why"><div><h3>Shop Neemuch locally</h3><p>Compare products from participating local stores in one place instead of searching shop by shop.</p></div><div><h3>Current local catalogue</h3><p>These product links are generated from Vibe4You's currently published seller catalogue.</p></div><div><h3>Fast local delivery</h3><p>Same Day Delivery is available inside the supported Neemuch service area, subject to product and delivery availability.</p></div></section>
<section class="more"><h2>More shopping in Neemuch</h2><div class="more-links">{related}</div></section>
</main>
<footer>Vibe4You · Your City. Your Shop. Your Style. · Neemuch, Madhya Pradesh</footer>
</body>
</html>"""

    def _merchant_feed_body(self) -> str:
        origin = self._seo_origin()
        if not origin:
            raise ApiError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "Merchant feed is unavailable.",
                "merchant_feed_unavailable",
            )

        products = self._with_live_inventory(self._shops().list_published_products())

        def clean(value: Any) -> str:
            return " ".join(str(value or "").split())

        def xml_text(value: Any) -> str:
            return xml_escape(clean(value))

        def absolute_url(value: Any) -> str:
            raw = clean(value)
            if raw.startswith(("https://", "http://")):
                return raw
            if not raw:
                return ""
            return origin + (raw if raw.startswith("/") else "/" + raw)

        items: list[str] = []
        for product in products:
            if product.get("active") is not True:
                continue
            product_id = clean(product.get("id"))
            slug = clean(product.get("slug"))
            name = clean(product.get("name"))
            if not product_id or not slug or not name:
                continue

            description = clean(
                product.get("description")
                or product.get("shortDescription")
                or f"Buy {name} from a local Neemuch store on Vibe4You."
            )
            description = description[:5000]
            product_link = origin + "/product/" + slug

            product_images = [
                absolute_url(value)
                for value in (product.get("images") or [])
                if absolute_url(value)
            ]
            if not product_images:
                thumbnail = absolute_url(product.get("thumbnail"))
                if thumbnail:
                    product_images = [thumbnail]
            if not product_images:
                continue

            category = clean(product.get("category"))
            subcategory = clean(product.get("subcategory"))
            product_type = " > ".join(value for value in (category, subcategory) if value)
            department = clean(product.get("department")).casefold()
            store_name = clean(product.get("storeName"))
            brand = clean(product.get("brand"))
            actual_brand = brand if brand and brand.casefold() != store_name.casefold() else ""

            variants = [
                variant
                for variant in (product.get("variants") or [])
                if variant.get("active") is not False
            ]
            if not variants:
                variants = [{
                    "id": product_id,
                    "size": "",
                    "colourName": "",
                    "stock": 0,
                    "price": product.get("price"),
                    "images": product_images,
                }]

            multiple_variants = len(variants) > 1
            for variant in variants:
                variant_id = clean(variant.get("id")) or product_id
                size = clean(variant.get("size"))
                colour = clean(variant.get("colourName"))

                title_parts = [name]
                if colour and colour.casefold() not in name.casefold():
                    title_parts.append(colour)
                if (
                    size
                    and size.casefold() not in {"default", "na", "n/a"}
                    and size.casefold() not in name.casefold()
                ):
                    title_parts.append(size)
                item_title = " - ".join(title_parts)[:150]

                try:
                    price = float(variant.get("price") or product.get("price"))
                except (TypeError, ValueError):
                    continue
                if not math.isfinite(price) or price <= 0:
                    continue

                try:
                    in_stock = int(variant.get("stock") or 0) > 0
                except (TypeError, ValueError):
                    in_stock = False

                variant_images = [
                    absolute_url(value)
                    for value in (variant.get("images") or [])
                    if absolute_url(value)
                ]
                images = variant_images or product_images

                parts = [
                    "<item>",
                    f"<g:id>{xml_text(variant_id if multiple_variants else product_id)}</g:id>",
                    f"<title>{xml_text(item_title)}</title>",
                    f"<link>{xml_text(product_link)}</link>",
                    f"<description>{xml_text(description)}</description>",
                    f"<g:image_link>{xml_text(images[0])}</g:image_link>",
                    f"<g:availability>{'in_stock' if in_stock else 'out_of_stock'}</g:availability>",
                    f"<g:price>{price:.2f} INR</g:price>",
                    "<g:condition>new</g:condition>",
                ]

                for extra_image in images[1:11]:
                    parts.append(f"<g:additional_image_link>{xml_text(extra_image)}</g:additional_image_link>")

                if actual_brand:
                    parts.append(f"<g:brand>{xml_text(actual_brand)}</g:brand>")
                else:
                    parts.append("<g:identifier_exists>no</g:identifier_exists>")

                if multiple_variants:
                    parts.append(f"<g:item_group_id>{xml_text(product_id)}</g:item_group_id>")
                if colour:
                    parts.append(f"<g:color>{xml_text(colour)}</g:color>")
                if size and size.casefold() not in {"default", "na", "n/a"}:
                    parts.append(f"<g:size>{xml_text(size)}</g:size>")
                if product_type:
                    parts.append(f"<g:product_type>{xml_text(product_type)}</g:product_type>")

                if department == "men":
                    parts.extend(("<g:gender>male</g:gender>", "<g:age_group>adult</g:age_group>"))
                elif department == "women":
                    parts.extend(("<g:gender>female</g:gender>", "<g:age_group>adult</g:age_group>"))
                elif department == "kids":
                    parts.append("<g:age_group>kids</g:age_group>")

                parts.append("</item>")
                items.append("".join(parts))

        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">\n'
            "<channel>"
            "<title>Vibe4You Neemuch Product Feed</title>"
            f"<link>{xml_text(origin)}</link>"
            "<description>Products available from Vibe4You local stores in Neemuch.</description>"
            + "".join(items)
            + "</channel>\n</rss>\n"
        )

    def _error_response(self, error: ApiError) -> None:
        self._json_response(error.status, {"success": False, "error": error.message, "code": error.code})

    def _security_error(self, error: SecurityError) -> None:
        self._json_response(error.status, {"success": False, "error": error.message, "code": error.code})

    def _security(self) -> SecurityStore:
        if self.payment_service.security is None:
            raise SecurityError(HTTPStatus.SERVICE_UNAVAILABLE, "Authentication is unavailable.", "authentication_unavailable")
        return self.payment_service.security

    def _shops(self) -> ShopWorkflow:
        if self.payment_service.shops is None:
            raise SecurityError(
                HTTPStatus.SERVICE_UNAVAILABLE,
                "Shop applications are unavailable.",
                "shop_service_unavailable",
            )
        return self.payment_service.shops

    def _reviews(self) -> ReviewWorkflow:
        if self.review_workflow is None:
            raise SecurityError(HTTPStatus.SERVICE_UNAVAILABLE, "Reviews are unavailable.", "review_service_unavailable")
        return self.review_workflow

    def _session_token(self) -> str | None:
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except Exception:
            return None
        morsel = cookie.get(COOKIE_NAME)
        return morsel.value if morsel else None

    def _current_user(self) -> tuple[dict[str, Any], Any]:
        return self._security().authenticate(self._session_token())

    def _payment_test_user(self) -> dict[str, Any]:
        try:
            user, _session = self._current_user()
        except SecurityError:
            raise ApiError(HTTPStatus.NOT_FOUND, "Not found.", "not_found") from None
        if not self.payment_service.can_access_payment_test_product(user):
            raise ApiError(HTTPStatus.NOT_FOUND, "Not found.", "not_found")
        return user

    def _csrf(self) -> None:
        origin = self.headers.get("Origin")
        expected_origin = os.environ.get("STYLEDASH_PUBLIC_ORIGIN", "").rstrip("/")
        if origin and expected_origin and origin.rstrip("/") != expected_origin:
            raise SecurityError(403, "Request origin is not allowed.", "invalid_origin")
        self._security().verify_csrf(self._session_token(), self.headers.get("X-CSRF-Token"))

    def _auth_payload(self, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        user, _session = self._current_user()
        self._csrf()
        trusted = dict(payload)
        trusted["userId"] = user["id"]
        trusted.pop("role", None)
        trusted.pop("paymentStatus", None)
        return user, trusted

    def _client_key(self, route: str) -> str:
        """Rate-limit/login identity. Never derived from X-Forwarded-For."""
        peer = self.client_address[0]
        client = peer
        source = os.environ.get(CLIENT_IP_SOURCE_ENV, "").strip().lower()
        if source == CLIENT_IP_SOURCE_CLOUDFLARE and peer in LOOPBACK_PEERS:
            client = cloudflare_client_identity(self.headers.get_all("CF-Connecting-IP")) or peer
        return f"{route}:{client}"

    def _read_json(self, maximum_bytes: int = MAX_BODY_BYTES) -> dict[str, Any]:
        raw_body = self._read_raw_body(maximum_bytes)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError(HTTPStatus.BAD_REQUEST, "Malformed JSON request.", "malformed_request") from None
        if not isinstance(payload, dict):
            raise ApiError(HTTPStatus.BAD_REQUEST, "A JSON object is required.", "malformed_request")
        return payload

    def _read_raw_body(self, maximum_bytes: int = MAX_BODY_BYTES) -> bytes:
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise ApiError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Content-Type must be application/json.", "invalid_content_type")
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise ApiError(HTTPStatus.LENGTH_REQUIRED, "Content-Length is required.", "length_required")
        try:
            length = int(raw_length)
        except ValueError:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid Content-Length.", "malformed_request") from None
        if length <= 0 or length > maximum_bytes:
            raise ApiError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Request body is too large.", "body_too_large")
        return self.rfile.read(length)

    def _rate_limit(self, route: str, limit: int) -> None:
        raw_multiplier = os.environ.get("STYLEDASH_E2E_RATE_LIMIT_MULTIPLIER", "1")
        try:
            multiplier = max(1, min(int(raw_multiplier), 100))
        except (TypeError, ValueError):
            multiplier = 1
        effective_limit = limit * multiplier
        if not self.rate_limiter.allow(self._client_key(route), effective_limit):
            raise ApiError(HTTPStatus.TOO_MANY_REQUESTS, "Too many requests. Please wait and try again.", "rate_limited")

    def _password_reset_rate_limit(self, payload: dict[str, Any]) -> None:
        """Apply IP and non-plaintext normalized-email limits without disclosure."""
        self._rate_limit("/api/auth/password-reset/request", 5)
        try:
            email = normalize_email(payload.get("email"))
        except SecurityError:
            return
        account_key = f"password-reset-email:{token_hash(email)}"
        if not self.rate_limiter.allow(account_key, 3):
            raise ApiError(HTTPStatus.TOO_MANY_REQUESTS, "Too many requests. Please wait and try again.", "rate_limited")

    def _handle_internal_admin_refund(self, path: str) -> bool:
        if path != "/api/internal-admin/refund-cancel":
            return False

        hostname = (self._request_hostname() or "").lower()
        peer = self.client_address[0]
        if peer not in ("127.0.0.1", "::1") or hostname not in {"127.0.0.1", "localhost", "::1"}:
            self._json_response(
                HTTPStatus.NOT_FOUND,
                {"success": False, "error": "Not found.", "code": "not_found"},
            )
            return True

        expected = ensure_admin_refund_token(self.payment_service.store.path.parent)
        supplied = self.headers.get("X-Vibe4You-Admin-Refund-Token", "")
        if (
            not isinstance(supplied, str)
            or not supplied
            or not hmac.compare_digest(expected, supplied)
        ):
            self._json_response(
                HTTPStatus.NOT_FOUND,
                {"success": False, "error": "Not found.", "code": "not_found"},
            )
            return True

        payload = self._read_json()
        order_id = payload.get("orderId")
        requested_by = payload.get("requestedBy")
        if not isinstance(order_id, str) or not order_id.strip():
            raise ApiError(HTTPStatus.BAD_REQUEST, "Order reference is required.", "order_not_found")
        if not isinstance(requested_by, str) or not requested_by.strip():
            raise ApiError(HTTPStatus.BAD_REQUEST, "Administrator reference is required.", "invalid_admin_reference")
        result = self.payment_service.initiate_full_refund_for_cancellation(
            order_id.strip(),
            requested_by.strip()[:128],
            payload.get("reason"),
        )
        self._json_response(HTTPStatus.OK, result)
        return True

    def do_GET(self) -> None:  # noqa: N802 - stdlib override name
        parsed = urlsplit(self.path)
        path = parsed.path
        try:
            if self._redirect_http_to_https():
                return
            if self._redirect_to_canonical_host():
                return
            if self._sensitive_path(path):
                self._json_response(HTTPStatus.NOT_FOUND, {"success": False, "error": "Not found.", "code": "not_found"})
                return
            if path.startswith("/media/product-images/"):
                self._serve_product_image(path)
                return
            if path == "/payment-test" or path.startswith("/payment-test/"):
                if path != PAYMENT_TEST_ROUTE:
                    raise ApiError(HTTPStatus.NOT_FOUND, "Not found.", "not_found")
                self._rate_limit(path, 30)
                self._payment_test_user()
                super().do_GET()
                return
            if path in NEEMUCH_LOCAL_PAGES:
                self._text_response(HTTPStatus.OK, self._neemuch_landing_body(path), "text/html; charset=utf-8")
                return
            if path == "/robots.txt":
                self._text_response(HTTPStatus.OK, self._robots_body(), "text/plain; charset=utf-8")
                return
            if path == "/sitemap.xml":
                self._text_response(HTTPStatus.OK, self._sitemap_body(), "application/xml; charset=utf-8")
                return
            if path == "/google-merchant-feed.xml":
                self._text_response(
                    HTTPStatus.OK,
                    self._merchant_feed_body(),
                    "application/rss+xml; charset=utf-8",
                )
                return
            if path == "/api/health":
                self._json_response(HTTPStatus.OK, self.payment_service.health())
                return
            if path == "/api/serviceability":
                self._rate_limit(path, 60)
                query = parse_qs(parsed.query, keep_blank_values=True)
                pincode_values = query.get("pincode", [])
                pincode = pincode_values[0] if len(pincode_values) == 1 else None

                def optional_coordinate(name: str) -> float | None:
                    values = query.get(name, [])
                    if not values:
                        return None
                    if len(values) != 1:
                        raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid delivery coordinates.", "invalid_location")
                    try:
                        value = float(values[0])
                    except (TypeError, ValueError):
                        raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid delivery coordinates.", "invalid_location") from None
                    if not math.isfinite(value):
                        raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid delivery coordinates.", "invalid_location")
                    return value

                latitude = optional_coordinate("latitude")
                longitude = optional_coordinate("longitude")
                self._json_response(
                    HTTPStatus.OK,
                    self.payment_service.check_serviceability(
                        pincode, latitude=latitude, longitude=longitude
                    ),
                )
                return
            if path == "/api/inventory/availability":
                self._rate_limit(path, 60)
                query = parse_qs(parsed.query, keep_blank_values=True)
                variant_values = query.get("variantId", [])
                product_values = query.get("productId", [])
                variant_id = variant_values[0] if len(variant_values) == 1 else None
                product_ids = product_values or None
                if len(variant_values) > 1:
                    raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid product option.", "invalid_variant")
                self._json_response(
                    HTTPStatus.OK,
                    self.payment_service.public_inventory_availability(variant_id, product_ids),
                )
                return
            if path == "/api/stores/active":
                self._rate_limit(path, 60)
                self._json_response(HTTPStatus.OK, {"success": True, "stores": self._shops().list_active_stores()})
                return
            if path == "/api/shop-products/homepage":
                self._rate_limit(path, 120)
                products = _homepage_product_candidates(self._shops().list_published_products())
                self._json_response(
                    HTTPStatus.OK,
                    {"success": True, "products": [_homepage_product_projection(product) for product in products]},
                )
                return
            if path == "/api/shop-products/published":
                self._rate_limit(path, 60)
                query = parse_qs(parsed.query, keep_blank_values=True)
                slug_values = query.get("slug", [])
                store_values = query.get("vendorId", [])
                if len(slug_values) > 1 or len(store_values) > 1 or (slug_values and store_values):
                    raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid catalogue request.", "invalid_catalogue_request")
                if slug_values:
                    product = self._with_live_inventory(
                        [self._shops().get_published_product(slug_values[0])]
                    )[0]
                    self._json_response(HTTPStatus.OK, {"success": True, "product": product})
                    return
                if store_values:
                    store_products = self._with_live_inventory(
                        self._shops().list_store_published_products(store_values[0])
                    )
                    self._json_response(HTTPStatus.OK, {"success": True, "products": store_products})
                    return
                products = self._with_live_inventory(self._shops().list_published_products())
                self._json_response(
                    HTTPStatus.OK,
                    {"success": True, "products": products},
                )
                return
            if path == "/api/shop-products/similar":
                self._rate_limit(path, 120)
                query = parse_qs(parsed.query, keep_blank_values=True)
                slug_values = query.get("slug", [])
                limit_values = query.get("limit", [])
                if len(slug_values) != 1 or len(limit_values) > 1:
                    raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid similar products request.", "invalid_similar_request")
                limit = 8
                if limit_values:
                    try:
                        limit = int(limit_values[0])
                    except ValueError:
                        raise ApiError(HTTPStatus.BAD_REQUEST, "Invalid similar products request.", "invalid_similar_request") from None
                similar = self._shops().list_similar_products(slug_values[0], limit)
                self._json_response(
                    HTTPStatus.OK,
                    {"success": True, "products": [_homepage_product_projection(product) for product in similar]},
                )
                return
            if path == f"/api/payment-test-product/{PAYMENT_TEST_PRODUCT_SLUG}":
                self._rate_limit(path, 30)
                user = self._payment_test_user()
                self._json_response(HTTPStatus.OK, self.payment_service.payment_test_product(user))
                return
            if path.startswith("/api/review-photo/"):
                self._rate_limit("review-photo:get", 180)
                review_id = unquote(path.removeprefix("/api/review-photo/"))
                blob = self._reviews().review_photo(review_id)
                self._binary_response(HTTPStatus.OK, blob, "image/webp",
                                      {"X-Content-Type-Options": "nosniff",
                                       "Content-Security-Policy": "default-src 'none'"})
                return
            if path == "/api/reviews":
                self._rate_limit("reviews:list", 120)
                query = parse_qs(parsed.query, keep_blank_values=True)
                product_values = query.get("productId", [])
                sort_values = query.get("sort", ["newest"])
                if len(product_values) != 1 or len(sort_values) != 1:
                    raise SecurityError(400, "Invalid review request.", "invalid_review_request")
                result = self._reviews().list_product(product_values[0], sort_values[0])
                self._json_response(HTTPStatus.OK, {"success": True, **result})
                return
            if path == "/api/store-reviews":
                self._rate_limit("store-reviews:list", 120)
                query = parse_qs(parsed.query, keep_blank_values=True)
                store_values = query.get("storeId", [])
                sort_values = query.get("sort", ["newest"])
                if len(store_values) != 1 or len(sort_values) != 1:
                    raise SecurityError(400, "Invalid local store review request.", "invalid_store_review_request")
                result = self._reviews().list_store(store_values[0], sort_values[0])
                self._json_response(HTTPStatus.OK, {"success": True, **result})
                return
            if path == "/api/reviews/summaries":
                self._rate_limit("reviews:summaries", 240)
                query = parse_qs(parsed.query, keep_blank_values=True)
                product_values = query.get("productId", [])
                result = self._reviews().summaries(product_values)
                self._json_response(HTTPStatus.OK, {"success": True, "summaries": result})
                return
            if path == "/api/reviews/eligibility":
                self._rate_limit("reviews:eligibility", 60)
                user, _session = self._current_user()
                query = parse_qs(parsed.query, keep_blank_values=True)
                product_values = query.get("productId", [])
                if len(product_values) != 1:
                    raise SecurityError(400, "Invalid product.", "invalid_product")
                result = self._reviews().eligibility(self.payment_service.store, user["id"], product_values[0])
                self._json_response(HTTPStatus.OK, {"success": True, **result})
                return
            if path == "/api/store-reviews/eligibility":
                self._rate_limit("store-reviews:eligibility", 60)
                user, _session = self._current_user()
                query = parse_qs(parsed.query, keep_blank_values=True)
                store_values = query.get("storeId", [])
                if len(store_values) != 1:
                    raise SecurityError(400, "Invalid local store review request.", "invalid_store_review_request")
                result = self._reviews().store_eligibility(self.payment_service.store, user["id"], store_values[0])
                self._json_response(HTTPStatus.OK, {"success": True, **result})
                return
            if path == "/api/auth/me":
                raw = self._session_token()
                user, _session = self._current_user()
                profile = self._security().profile(user["id"])
                self._json_response(HTTPStatus.OK, {"success": True, "user": profile, "csrfToken": self._security().csrf_token(raw or "")})
                return
            if path == "/api/account-state":
                self._rate_limit(path, 120)
                user, _session = self._current_user()
                state = self._security().account_state(user["id"])
                self._json_response(HTTPStatus.OK, {"success": True, **state})
                return
            if path == "/api/outside-delivery-requests":
                user, _session = self._current_user()
                requests = self.payment_service.list_delivery_requests(user["id"])
                self._json_response(HTTPStatus.OK, {"success": True, "requests": requests})
                return
            if path == "/api/orders":
                user, _session = self._current_user()
                orders = self._security().list_orders(self.payment_service.store, user["id"])
                display_orders = [self.payment_service.order_for_display(order) for order in orders]
                self._json_response(HTTPStatus.OK, {"success": True, "orders": display_orders})
                return
            if path == "/api/profile":
                user, _session = self._current_user()
                self._json_response(HTTPStatus.OK, {"success": True, "profile": self._security().profile(user["id"])})
                return
            if path == "/api/vendor-applications/me":
                user, _session = self._current_user()
                self._json_response(
                    HTTPStatus.OK,
                    {"success": True, "application": self._shops().get_application(user["id"])},
                )
                return
            if path == "/api/shop-products":
                user, _session = self._current_user()
                products = self._shops().list_products(user["id"])
                live_inventory = self.payment_service.shop_inventory_snapshot(
                    [product["id"] for product in products if product["status"] == "PUBLISHED"]
                )
                for product in products:
                    for variant in product.get("variants", []):
                        stock = live_inventory.get(variant["id"])
                        if stock is not None:
                            variant["inventory"] = stock
                    if product.get("variants"):
                        product["inventory"] = sum(item["inventory"] for item in product["variants"])
                self._json_response(
                    HTTPStatus.OK,
                    {"success": True, "products": products},
                )
                return
            if path == "/api/shop-product-requests":
                user, _session = self._current_user()
                self._json_response(
                    HTTPStatus.OK,
                    {
                        "success": True,
                        "requests": self._shops().list_product_change_requests(user["id"]),
                    },
                )
                return
            if path.startswith("/api/orders/") and path.endswith("/tax-invoice-status"):
                user, _session = self._current_user()
                order_id = unquote(path.removeprefix("/api/orders/").removesuffix("/tax-invoice-status"))
                self._security().get_order(self.payment_service.store, order_id, user["id"])
                invoices = InvoiceGateway(self.payment_service.store.path.parent)
                self._json_response(HTTPStatus.OK, {
                    "success":True,
                    "issued": invoices.issued_for_order(order_id) is not None,
                })
                return
            if path.startswith("/api/orders/") and path.endswith("/tax-invoice"):
                user, _session = self._current_user()
                order_id = unquote(path.removeprefix("/api/orders/").removesuffix("/tax-invoice"))
                # Authenticate ownership BEFORE fetching the separate invoice ledger.
                self._security().get_order(self.payment_service.store, order_id, user["id"])
                invoices = InvoiceGateway(self.payment_service.store.path.parent)
                try:
                    pdf = invoices.download_issued(order_id)
                except InvoiceDraftError as exc:
                    raise ApiError(HTTPStatus.CONFLICT, str(exc), "tax_invoice_not_ready") from None
                safe_id = re.sub(r"[^A-Za-z0-9_-]+", "-", order_id)[:80] or "order"
                self._binary_response(HTTPStatus.OK, pdf, "application/pdf",
                    {"Content-Disposition": f'attachment; filename="vibe4you-tax-invoice-{safe_id}.pdf"'})
                return
            if path.startswith("/api/orders/") and path.endswith("/receipt"):
                user, _session = self._current_user()
                order_id = unquote(path.removeprefix("/api/orders/").removesuffix("/receipt"))
                order = self._security().get_order(self.payment_service.store, order_id, user["id"])
                pdf = self.payment_service.receipt_pdf(order)
                safe_id = re.sub(r"[^A-Za-z0-9_-]+", "-", order_id)[:80] or "order"
                self._binary_response(HTTPStatus.OK, pdf, "application/pdf", {"Content-Disposition": f'attachment; filename="vibe4you-receipt-{safe_id}.pdf"'})
                return
            if path.startswith("/api/orders/"):
                user, _session = self._current_user()
                order_id = unquote(path.removeprefix("/api/orders/"))
                order = self._security().get_order(self.payment_service.store, order_id, user["id"])
                self._json_response(HTTPStatus.OK, {"success": True, "order": self.payment_service.order_for_display(order)})
                return
            if path.startswith(API_PREFIX):
                self._json_response(HTTPStatus.NOT_FOUND, {"success": False, "error": "API endpoint not found.", "code": "not_found"})
                return
            super().do_GET()
        except ApiError as error:
            self._error_response(error)
        except SecurityError as error:
            self._security_error(error)

    def do_HEAD(self) -> None:  # noqa: N802 - stdlib override name
        path = urlsplit(self.path).path
        if self._redirect_http_to_https():
            return
        if self._redirect_to_canonical_host():
            return
        if self._sensitive_path(path):
            self._json_response(HTTPStatus.NOT_FOUND, {"success": False, "error": "Not found.", "code": "not_found"}, head_only=True)
            return
        if path.startswith("/media/product-images/"):
            try:
                self._serve_product_image(path, head_only=True)
            except ApiError as error:
                self._json_response(error.status, {"success": False, "error": error.message, "code": error.code}, head_only=True)
            return
        if path == "/payment-test" or path.startswith("/payment-test/"):
            if path != PAYMENT_TEST_ROUTE:
                self._json_response(HTTPStatus.NOT_FOUND, {"success": False, "error": "Not found.", "code": "not_found"}, head_only=True)
                return
            try:
                self._payment_test_user()
            except (ApiError, SecurityError):
                self._json_response(HTTPStatus.NOT_FOUND, {"success": False, "error": "Not found.", "code": "not_found"}, head_only=True)
                return
            super().do_HEAD()
            return
        if path in NEEMUCH_LOCAL_PAGES:
            try:
                body = self._neemuch_landing_body(path)
            except ApiError as error:
                self._json_response(error.status, {"success": False, "error": error.message, "code": error.code}, head_only=True)
                return
            self._text_response(HTTPStatus.OK, body, "text/html; charset=utf-8", head_only=True)
            return
        if path == "/robots.txt":
            self._text_response(HTTPStatus.OK, self._robots_body(), "text/plain; charset=utf-8", head_only=True)
            return
        if path == "/sitemap.xml":
            try:
                body = self._sitemap_body()
            except ApiError as error:
                self._json_response(error.status, {"success": False, "error": error.message, "code": error.code}, head_only=True)
                return
            self._text_response(HTTPStatus.OK, body, "application/xml; charset=utf-8", head_only=True)
            return
        if path == "/google-merchant-feed.xml":
            try:
                body = self._merchant_feed_body()
            except ApiError as error:
                self._json_response(error.status, {"success": False, "error": error.message, "code": error.code}, head_only=True)
                return
            self._text_response(HTTPStatus.OK, body, "application/rss+xml; charset=utf-8", head_only=True)
            return
        if path == "/api/health":
            self._json_response(HTTPStatus.OK, self.payment_service.health(), head_only=True)
            return
        if path.startswith(API_PREFIX):
            self._json_response(HTTPStatus.METHOD_NOT_ALLOWED, {"success": False, "error": "Method not allowed.", "code": "method_not_allowed"}, head_only=True)
            return
        super().do_HEAD()

    def do_POST(self) -> None:  # noqa: N802 - stdlib override name
        path = urlsplit(self.path).path
        try:
            if self._handle_internal_admin_refund(path):
                return
            if self._redirect_http_to_https():
                return
            if self._sensitive_path(path):
                self._json_response(HTTPStatus.NOT_FOUND, {"success": False, "error": "Not found.", "code": "not_found"})
                return
            if path == "/api/outside-delivery-requests":
                self._rate_limit(path, 10)
                user, _session = self._current_user()
                self._csrf()
                result = self.payment_service.create_delivery_request(user["id"], self._read_json())
                if not result.get("idempotent"):
                    request = result.get("request") or {}
                    owner_notifier().send(
                        event="outside_delivery_request",
                        title="Outside Neemuch Delivery Request",
                        message=(
                            f"Request: {request.get('id') or '-'}\n"
                            f"Product: {request.get('productName') or '-'}\n"
                            f"Destination: {(request.get('address') or {}).get('city') or '-'} - {(request.get('address') or {}).get('pincode') or '-'}\n"
                            "Status: Delivery quote required"
                        ),
                        priority=5,
                        tags=["package"],
                    )
                self._json_response(
                    HTTPStatus.OK if result.get("idempotent") else HTTPStatus.CREATED,
                    {"success": True, **result},
                )
                return
            outside_payment_match = re.fullmatch(r"/api/outside-delivery-requests/([^/]+)/create-order", path)
            if outside_payment_match:
                self._rate_limit("/api/outside-delivery-requests/create-order", 10)
                user, _session = self._current_user()
                self._csrf()
                request_id = unquote(outside_payment_match.group(1))
                result = self.payment_service.create_delivery_request_order(
                    user["id"], request_id, self._read_json(), self.headers.get("Idempotency-Key")
                )
                self._json_response(HTTPStatus.CREATED, result)
                return
            outside_cancel_match = re.fullmatch(r"/api/outside-delivery-requests/([^/]+)/cancel", path)
            if outside_cancel_match:
                self._rate_limit("/api/outside-delivery-requests/cancel", 10)
                user, _session = self._current_user()
                self._csrf()
                self._read_json()
                request_id = unquote(outside_cancel_match.group(1))
                request = self.payment_service.cancel_delivery_request(user["id"], request_id)
                self._json_response(HTTPStatus.OK, {"success": True, "request": request})
                return
            if path == "/api/create-order":
                self._rate_limit(path, 10)
                _user, payload = self._auth_payload(self._read_json())
                result = self.payment_service.create_razorpay_order(
                    payload, self.headers.get("Idempotency-Key")
                )
                self._json_response(HTTPStatus.CREATED, result)
                return
            if path == f"/api/payment-test-product/{PAYMENT_TEST_PRODUCT_SLUG}/create-order":
                self._rate_limit(path, 5)
                user = self._payment_test_user()
                self._csrf()
                result = self.payment_service.create_payment_test_order(
                    user,
                    self._read_json(),
                    self.headers.get("Idempotency-Key"),
                )
                self._json_response(HTTPStatus.CREATED, result)
                return
            if path == "/api/verify-payment":
                self._rate_limit(path, 20)
                user, payload = self._auth_payload(self._read_json())
                self._security().get_order(self.payment_service.store, str(payload.get("styleDashOrderId", "")), user["id"])
                result = self.payment_service.verify_payment(payload)
                self._json_response(HTTPStatus.OK, result)
                return
            if path == "/api/webhooks/razorpay":
                self._rate_limit(path, 120)
                result = self.payment_service.process_webhook(
                    self._read_raw_body(),
                    self.headers.get("X-Razorpay-Signature"),
                    self.headers.get("X-Razorpay-Event-Id"),
                )
                self._json_response(HTTPStatus.OK, result)
                return
            if path == "/api/place-cod-order":
                self._rate_limit(path, 10)
                _user, payload = self._auth_payload(self._read_json())
                result = self.payment_service.place_cod_order(
                    payload, self.headers.get("Idempotency-Key")
                )
                if not result["idempotent"]:
                    # Order and stock are already durable; notification is best-effort.
                    _notify_cod_order_placed(result["order"])
                self._json_response(
                    HTTPStatus.OK if result["idempotent"] else HTTPStatus.CREATED,
                    result,
                )
                return
            if path.startswith("/api/orders/") and path.endswith("/try-at-home"):
                self._rate_limit("/api/orders/try-at-home", 20)
                user, _session = self._current_user()
                self._csrf()
                order_id = unquote(path.removeprefix("/api/orders/").removesuffix("/try-at-home"))
                if not order_id or "/" in order_id:
                    raise SecurityError(404, "Order not found.", "order_not_found")
                payload = self._read_json()
                order = self.payment_service.finalize_try_at_home(order_id, user["id"], payload.get("itemIndex"), payload.get("keptVariantId"))
                self._json_response(HTTPStatus.OK, {"success": True, "order": order})
                return
            if path.startswith("/api/orders/") and path.endswith("/cancel-request"):
                self._rate_limit("/api/orders/cancel-request", 10)
                user, _session = self._current_user()
                self._csrf()
                order_id = unquote(path.removeprefix("/api/orders/").removesuffix("/cancel-request"))
                if not order_id or "/" in order_id:
                    raise SecurityError(404, "Order not found.", "order_not_found")
                self._read_json()
                result = self.payment_service.request_customer_cancellation(order_id, user["id"])
                self._json_response(HTTPStatus.OK, {"success": True, **result})
                return
            if path.startswith("/api/orders/") and path.endswith("/exchange-requests"):
                self._rate_limit("/api/orders/exchange-requests", 10)
                user, _session = self._current_user()
                self._csrf()
                order_id = unquote(path.removeprefix("/api/orders/").removesuffix("/exchange-requests"))
                if not order_id or "/" in order_id:
                    raise SecurityError(404, "Order not found.", "order_not_found")
                payload = self._read_json()
                result = self.payment_service.request_exchange(
                    order_id, user["id"], payload.get("itemIndex"), payload.get("targetVariantId")
                )
                self._json_response(
                    HTTPStatus.CREATED if not result["idempotent"] else HTTPStatus.OK,
                    {"success": True, "idempotent": result["idempotent"], "order": result["order"]},
                )
                return
            if path == "/api/reviews":
                self._rate_limit("reviews:create", 10)
                user, _session = self._current_user()
                self._csrf()
                payload = self._read_json(maximum_bytes=300_000)
                self._shops().get_published_product(payload.get("productId"))
                review = self._reviews().create(self.payment_service.store, user["id"], payload)
                self._json_response(HTTPStatus.CREATED, {"success": True, "review": review})
                return
            if path == "/api/store-reviews":
                self._rate_limit("store-reviews:create", 10)
                user, _session = self._current_user()
                self._csrf()
                review = self._reviews().create_store(self.payment_service.store, user["id"], self._read_json(maximum_bytes=300_000))
                self._json_response(HTTPStatus.CREATED, {"success": True, "review": review})
                return
            if path.startswith("/api/reviews/") and path.endswith("/edit"):
                self._rate_limit("reviews:edit", 10)
                user, _session = self._current_user()
                self._csrf()
                review_id = unquote(path.removeprefix("/api/reviews/").removesuffix("/edit"))
                if not review_id or "/" in review_id:
                    raise SecurityError(404, "Review not found.", "review_not_found")
                review = self._reviews().edit(user["id"], review_id, self._read_json(maximum_bytes=300_000))
                self._json_response(HTTPStatus.OK, {"success": True, "review": review})
                return
            if path.startswith("/api/store-reviews/") and path.endswith("/edit"):
                self._rate_limit("store-reviews:edit", 10)
                user, _session = self._current_user()
                self._csrf()
                review_id = unquote(path.removeprefix("/api/store-reviews/").removesuffix("/edit"))
                if not review_id or "/" in review_id:
                    raise SecurityError(404, "Store review not found.", "store_review_not_found")
                review = self._reviews().edit_store(user["id"], review_id, self._read_json(maximum_bytes=300_000))
                self._json_response(HTTPStatus.OK, {"success": True, "review": review})
                return
            if path.startswith("/api/reviews/") and path.endswith("/delete"):
                self._rate_limit("reviews:delete", 10)
                user, _session = self._current_user()
                self._csrf()
                review_id = unquote(path.removeprefix("/api/reviews/").removesuffix("/delete"))
                if not review_id or "/" in review_id:
                    raise SecurityError(404, "Review not found.", "review_not_found")
                self._reviews().delete(user["id"], review_id)
                self._json_response(HTTPStatus.OK, {"success": True})
                return
            if path.startswith("/api/store-reviews/") and path.endswith("/delete"):
                self._rate_limit("store-reviews:delete", 10)
                user, _session = self._current_user()
                self._csrf()
                review_id = unquote(path.removeprefix("/api/store-reviews/").removesuffix("/delete"))
                if not review_id or "/" in review_id:
                    raise SecurityError(404, "Store review not found.", "store_review_not_found")
                self._reviews().delete_store(user["id"], review_id)
                self._json_response(HTTPStatus.OK, {"success": True})
                return
            if path == "/api/auth/register":
                self._rate_limit(path, 5)
                if self.registration_verifier is not None:
                    payload = self._read_json()
                    email = normalize_email(payload.get("email"))
                    if not self.rate_limiter.allow("register-email:" + token_hash(email), 2):
                        raise SecurityError(429, "Too many registration requests. Try again later.", "rate_limited")
                    self.registration_verifier.begin(payload)
                    self._json_response(HTTPStatus.CONFLICT, {
                        "success": False, "code": "email_verification_sent",
                        "error": "If eligible, a verification link has been sent to your email. Check your inbox and spam folder. The link expires in 30 minutes.",
                    })
                    return
                user, raw, csrf = self._security().register(
                    self._read_json(), record_terms_acceptance=True
                )

                owner_notifier().send(
                    event="customer_registered",
                    title="New Vibe4You Registration",
                    message=(
                        f"Name: {user.get('name') or '-'}\n"
                        f"Email: {mask_email(user.get('email') or '')}\n"
                        f"Customer ID: {user.get('id') or '-'}"
                    ),
                    priority=5,
                    tags=["bust_in_silhouette"],
                )

                profile = self._security().profile(user["id"])
                self._json_response(
                    HTTPStatus.CREATED,
                    {
                        "success": True,
                        "user": profile,
                        "csrfToken": csrf,
                    },
                    headers={
                        "Set-Cookie": self._security().cookie(raw)
                    },
                )
                return
            if path == "/api/auth/register/confirm":
                self._rate_limit(path, 10)
                if self.registration_verifier is None:
                    raise SecurityError(404, "Not found.", "not_found")
                user, raw, csrf = self.registration_verifier.confirm(self._read_json())
                owner_notifier().send(
                    event="customer_registered",
                    title="New Vibe4You Registration",
                    message=(
                        f"Name: {user.get('name') or '-'}\n"
                        f"Email: {mask_email(user.get('email') or '')}\n"
                        f"Customer ID: {user.get('id') or '-'}"
                    ),
                    priority=5,
                    tags=["bust_in_silhouette"],
                )
                self._json_response(HTTPStatus.CREATED, {
                    "success": True, "user": self._security().profile(user["id"]), "csrfToken": csrf,
                }, headers={"Set-Cookie": self._security().cookie(raw)})
                return
            if path == "/api/auth/login":
                self._rate_limit(path, 12)
                user, raw, csrf = self._security().login(
                    self._read_json(), self._client_key("login"), record_terms_acceptance=True
                )
                profile = self._security().profile(user["id"])
                self._json_response(HTTPStatus.OK, {"success": True, "user": profile, "csrfToken": csrf}, headers={"Set-Cookie": self._security().cookie(raw)})
                return
            if path in ("/api/auth/federated/google", "/api/auth/federated/phone"):
                self._rate_limit(path, 10)
                provider = "google" if path.endswith("google") else "phone"
                user, raw, csrf, created = self._security().federated_session(
                    provider, self._read_json(), record_terms_acceptance=True
                )

                if created:
                    contact = (
                        f"Email: {mask_email(user.get('email') or '')}"
                        if provider == "google"
                        else f"Mobile: {mask_phone(user.get('phone') or '')}"
                    )
                    owner_notifier().send(
                        event="customer_registered",
                        title="New Vibe4You Registration",
                        message=(
                            f"Name: {user.get('name') or '-'}\n"
                            f"{contact}\n"
                            f"Method: {'Google' if provider == 'google' else 'Mobile OTP'}\n"
                            f"Customer ID: {user.get('id') or '-'}"
                        ),
                        priority=5,
                        tags=["bust_in_silhouette"],
                    )

                needs_profile = bool(user.get("needsProfile"))
                profile = self._security().profile(user["id"])
                self._json_response(
                    HTTPStatus.OK if not created else HTTPStatus.CREATED,
                    {
                        "success": True,
                        "user": profile,
                        "csrfToken": csrf,
                        "needsProfile": needs_profile,
                    },
                    headers={"Set-Cookie": self._security().cookie(raw)},
                )
                return
            if path in (
                "/api/auth/federated/google/link",
                "/api/auth/federated/phone/link",
                "/api/auth/federated/link/google",
                "/api/auth/federated/link/phone",
            ):
                self._rate_limit(path, 10)
                raw = self._session_token()
                self._security().verify_csrf(raw, self.headers.get("X-CSRF-Token"))
                provider = "google" if "/google" in path else "phone"
                profile = self._security().link_federated_identity(
                    raw or "", provider, self._read_json()
                )
                self._json_response(HTTPStatus.OK, {"success": True, "profile": profile})
                return
            if path == "/api/auth/password-reset/request":
                payload = self._read_json()
                self._password_reset_rate_limit(payload)
                self._security().request_password_reset(payload)
                self._json_response(HTTPStatus.OK, {"success": True, "message": "If an account exists, reset instructions will be sent shortly."})
                return
            if path == "/api/auth/password-reset/confirm":
                self._rate_limit(path, 10)
                self._security().confirm_password_reset(self._read_json())
                self._json_response(HTTPStatus.OK, {"success": True, "message": "Your password has been reset. Please sign in."})
                return
            if path == "/api/auth/logout":
                self._current_user()
                self._csrf()
                self._security().revoke(self._session_token() or "")
                self._json_response(HTTPStatus.OK, {"success": True}, headers={"Set-Cookie": self._security().clear_cookie()})
                return
            if path == "/api/auth/change-password":
                self._csrf()
                raw, csrf = self._security().change_password(self._session_token() or "", self._read_json())
                self._json_response(HTTPStatus.OK, {"success": True, "csrfToken": csrf}, headers={"Set-Cookie": self._security().cookie(raw)})
                return
            if path == "/api/auth/delete-account":
                # V4Y-054: self-service account deletion (identity from the session).
                self._rate_limit(path, 5)
                self._csrf()
                self._security().delete_account(
                    self._session_token() or "", self._read_json(), self.payment_service.store
                )
                self._json_response(
                    HTTPStatus.OK,
                    {"success": True},
                    headers={"Set-Cookie": self._security().clear_cookie()},
                )
                return
            if path == "/api/vendor-applications":
                self._rate_limit(path, 5)
                user, _session = self._current_user()
                self._csrf()
                vendor_payload = self._read_json()
                legacy_submit = "email" in vendor_payload or "phone" in vendor_payload
                safe_payload = {
                    key: value
                    for key, value in vendor_payload.items()
                    if key not in {"email", "phone"}
                }
                if "storeName" in safe_payload and "shopName" not in safe_payload:
                    safe_payload["shopName"] = safe_payload.pop("storeName")
                if legacy_submit:
                    # The original form represented an immediate submission
                    # and was Neemuch-only. Preserve that behavior while the
                    # new UI uses explicit draft + submit endpoints.
                    safe_payload.setdefault("city", "Neemuch")
                    safe_payload.setdefault("state", "Madhya Pradesh")
                result = self._shops().create_draft(user["id"], safe_payload)
                if legacy_submit:
                    result = self._shops().submit_application(user["id"])
                    owner_notifier().send(
                        event="vendor_application",
                        title="New Vendor Application",
                        message=(
                            f"Application: {result.get('id') or '-'}\n"
                            f"Store: {' '.join(str(result.get('shopName') or '-').split())[:100]}\n"
                            f"Category: {' '.join(str(result.get('category') or '-').split())[:80]}\n"
                            "Status: Submitted"
                        ),
                        priority=5,
                        tags=["briefcase"],
                    )
                self._json_response(
                    HTTPStatus.CREATED,
                    {"success": True, "application": result},
                )
                return
            if path == "/api/vendor-applications/me/submit":
                self._rate_limit(path, 5)
                user, _session = self._current_user()
                self._csrf()
                result = self._shops().submit_application(user["id"])
                owner_notifier().send(
                    event="vendor_application",
                    title="New Vendor Application",
                    message=(
                        f"Application: {result.get('id') or '-'}\n"
                        f"Store: {' '.join(str(result.get('shopName') or '-').split())[:100]}\n"
                        f"Category: {' '.join(str(result.get('category') or '-').split())[:80]}\n"
                        "Status: Submitted"
                    ),
                    priority=5,
                    tags=["briefcase"],
                )
                self._json_response(
                    HTTPStatus.OK, {"success": True, "application": result}
                )
                return
            if path in {"/api/shop-product-images", "/api/shop-branding-images"}:
                self._rate_limit(path, 8)
                self._require_product_image_seller()
                image = self._store_product_image(self._read_json(PRODUCT_IMAGE_REQUEST_MAX_BYTES))
                self._json_response(HTTPStatus.CREATED, {"success": True, "image": image})
                return
            if path == "/api/shop-products":
                self._rate_limit(path, 10)
                user, _session = self._current_user()
                self._csrf()
                result = self._shops().create_product_draft(user["id"], self._read_json())
                self._json_response(
                    HTTPStatus.CREATED, {"success": True, "product": result}
                )
                return
            if path.startswith("/api/shop-products/") and path.endswith("/submit"):
                self._rate_limit("/api/shop-products/submit", 10)
                user, _session = self._current_user()
                self._csrf()
                product_id = unquote(
                    path.removeprefix("/api/shop-products/").removesuffix("/submit")
                )
                if not product_id or "/" in product_id:
                    raise SecurityError(404, "Product submission not found.", "product_not_found")
                result = self._shops().submit_product(user["id"], product_id)
                _notify_shop_product_review(result=result, event="shop_product_submission", title="Shop Product Needs Review")
                self._json_response(
                    HTTPStatus.OK, {"success": True, "product": result}
                )
                return
            if path.startswith("/api/shop-products/") and path.endswith("/edit-request"):
                self._rate_limit("/api/shop-products/edit-request", 10)
                user, _session = self._current_user()
                self._csrf()
                product_id = unquote(
                    path.removeprefix("/api/shop-products/").removesuffix("/edit-request")
                )
                if not product_id or "/" in product_id:
                    raise SecurityError(404, "Product submission not found.", "product_not_found")
                live_inventory = self.payment_service.shop_inventory_snapshot([product_id])
                result = self._shops().create_product_edit_request(
                    user["id"], product_id, self._read_json(), live_inventory
                )
                _notify_shop_product_review(result=result, event="shop_product_change_request", title="Shop Product Change Needs Review", request_type="EDIT")
                self._json_response(
                    HTTPStatus.CREATED, {"success": True, "request": result}
                )
                return
            if path.startswith("/api/shop-products/") and path.endswith("/unpublish-request"):
                self._rate_limit("/api/shop-products/unpublish-request", 10)
                user, _session = self._current_user()
                self._csrf()
                product_id = unquote(
                    path.removeprefix("/api/shop-products/").removesuffix("/unpublish-request")
                )
                if not product_id or "/" in product_id:
                    raise SecurityError(404, "Product submission not found.", "product_not_found")
                payload = self._read_json()
                if payload:
                    raise SecurityError(
                        400,
                        "Unpublish requests do not accept product fields.",
                        "invalid_product_change",
                    )
                result = self._shops().create_product_unpublish_request(
                    user["id"], product_id
                )
                _notify_shop_product_review(result=result, event="shop_product_change_request", title="Shop Product Change Needs Review", request_type="UNPUBLISH")
                self._json_response(
                    HTTPStatus.CREATED, {"success": True, "request": result}
                )
                return
            if path.startswith(API_PREFIX):
                self._json_response(HTTPStatus.NOT_FOUND, {"success": False, "error": "API endpoint not found.", "code": "not_found"})
                return
            self._json_response(HTTPStatus.METHOD_NOT_ALLOWED, {"success": False, "error": "Method not allowed.", "code": "method_not_allowed"})
        except ApiError as error:
            self._error_response(error)
        except SecurityError as error:
            self._security_error(error)
        except Exception:
            self._json_response(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"success": False, "error": "The server could not process this request.", "code": "internal_error"},
            )

    def do_PUT(self) -> None:  # noqa: N802 - stdlib override name
        if self._redirect_http_to_https():
            return
        if self._sensitive_path(urlsplit(self.path).path):
            self._json_response(HTTPStatus.NOT_FOUND, {"success": False, "error": "Not found.", "code": "not_found"})
            return
        self._json_response(HTTPStatus.METHOD_NOT_ALLOWED, {"success": False, "error": "Method not allowed.", "code": "method_not_allowed"})

    def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib override name
        self.do_PUT()

    def do_TRACE(self) -> None:  # noqa: N802 - stdlib override name
        self.do_PUT()

    def do_DELETE(self) -> None:  # noqa: N802 - stdlib override name
        self.do_PUT()

    def do_PATCH(self) -> None:  # noqa: N802 - stdlib override name
        path = urlsplit(self.path).path
        try:
            if self._redirect_http_to_https():
                return
            if self._sensitive_path(path):
                self._json_response(HTTPStatus.NOT_FOUND, {"success": False, "error": "Not found.", "code": "not_found"})
                return
            if path == "/api/account-state/cart":
                self._rate_limit(path, 120)
                user, _session = self._current_user()
                self._csrf()
                cart = self._security().replace_cart(user["id"], self._read_json())
                self._json_response(HTTPStatus.OK, {"success": True, "cart": cart})
                return
            if path == "/api/account-state/wishlist":
                self._rate_limit(path, 120)
                user, _session = self._current_user()
                self._csrf()
                wishlist = self._security().replace_wishlist(user["id"], self._read_json())
                self._json_response(HTTPStatus.OK, {"success": True, "wishlist": wishlist})
                return
            if path == "/api/profile":
                self._rate_limit(path, 30)
                user, _session = self._current_user()
                self._csrf()
                profile = self._security().update_profile(user["id"], self._read_json())
                self._json_response(HTTPStatus.OK, {"success": True, "profile": profile})
                return
            if path == "/api/vendor-applications/me/branding":
                self._rate_limit(path, 20)
                user, _session = self._current_user()
                self._csrf()
                payload = self._read_json()
                self._require_uploaded_store_branding(payload)
                application = self._shops().update_store_branding(user["id"], payload)
                self._json_response(
                    HTTPStatus.OK, {"success": True, "application": application}
                )
                return
            if path == "/api/vendor-applications/me":
                self._rate_limit(path, 20)
                user, _session = self._current_user()
                self._csrf()
                application = self._shops().update_draft(user["id"], self._read_json())
                self._json_response(
                    HTTPStatus.OK, {"success": True, "application": application}
                )
                return
            if path.startswith("/api/shop-products/") and path.endswith("/stock"):
                self._rate_limit("/api/shop-products/stock", 30)
                user, _session = self._current_user()
                self._csrf()
                product_id = unquote(
                    path.removeprefix("/api/shop-products/").removesuffix("/stock")
                )
                if not product_id or "/" in product_id:
                    raise SecurityError(404, "Product submission not found.", "product_not_found")
                payload = self._read_json()
                if not isinstance(payload, dict) or set(payload) not in ({"stock"}, {"variantId", "stock"}):
                    raise SecurityError(
                        400,
                        "Provide the new stock value and, for multi-size products, its variantId.",
                        "invalid_inventory_adjustment",
                    )
                self._shops().require_seller_stock_update_allowed(user["id"], product_id)
                inventory = self.payment_service.set_shop_inventory(
                    product_id, payload.get("stock"), payload.get("variantId")
                )
                self._json_response(
                    HTTPStatus.OK, {"success": True, "inventory": inventory}
                )
                return
            if path.startswith("/api/shop-products/"):
                self._rate_limit("/api/shop-products", 20)
                user, _session = self._current_user()
                self._csrf()
                product_id = unquote(path.removeprefix("/api/shop-products/"))
                if not product_id or "/" in product_id:
                    raise SecurityError(404, "Product submission not found.", "product_not_found")
                product = self._shops().update_product_draft(
                    user["id"], product_id, self._read_json()
                )
                self._json_response(HTTPStatus.OK, {"success": True, "product": product})
                return
            self._json_response(HTTPStatus.METHOD_NOT_ALLOWED, {"success": False, "error": "Method not allowed.", "code": "method_not_allowed"})
        except ApiError as error:
            self._error_response(error)
        except SecurityError as error:
            self._security_error(error)

    def _spa_seo_shell_body(self, url_path: str) -> bytes | None:
        origin = self._seo_origin()
        if not origin:
            return None

        kind = None
        entity: dict[str, Any] | None = None
        slug = ""
        if url_path.startswith("/product/"):
            slug = unquote(url_path.removeprefix("/product/")).strip()
            if not slug or "/" in slug:
                return None
            if len(slug) > 128:
                return None
            product = self._seo_public_product(slug)
            if product is None:
                return None
            entity = self._with_live_inventory([product])[0]
            kind = "product"
        elif url_path.startswith("/store/"):
            slug = unquote(url_path.removeprefix("/store/")).strip()
            if not slug or "/" in slug:
                return None
            store = self._seo_public_store(slug)
            if store is None:
                return None
            entity = store
            kind = "store"
        elif url_path in SPA_PAGE_SEO:
            kind = "page"
            slug = url_path
        else:
            return None

        index_path = Path(self.translate_path("/index.html"))
        try:
            html = index_path.read_text(encoding="utf-8")
        except OSError:
            return None

        def clean(value: Any) -> str:
            return " ".join(str(value or "").split())

        def html_attr(value: Any) -> str:
            return xml_escape(clean(value), {'"': "&quot;", "'": "&#39;"})

        def seo_title(label: Any, *, prefix: str = "", suffix: str = "", limit: int = 65) -> str:
            value = clean(label)
            budget = max(1, limit - len(prefix) - len(suffix))
            if len(value) > budget:
                shortened = value[:budget + 1].rsplit(" ", 1)[0].rstrip(" -,:;/")
                value = shortened if shortened else value[:budget].rstrip(" -,:;/")
            return clean(f"{prefix}{value}{suffix}")[:limit]

        def absolute_url(value: Any) -> str:
            raw = clean(value)
            if raw.startswith(("https://", "http://")):
                return raw
            if not raw:
                return ""
            return origin + (raw if raw.startswith("/") else "/" + raw)

        canonical = origin + url_path
        structured_graph: list[dict[str, Any]]

        if kind == "product":
            product = entity
            name = clean(product.get("name")) or "Product"
            heading = name
            store_name = clean(product.get("storeName")) or "Local Neemuch store"
            short_description = clean(product.get("shortDescription") or product.get("description"))
            description = clean(
                f"Shop {name} from {store_name} in Neemuch on Vibe4You. {short_description}"
            )[:300]
            title = seo_title(name, prefix="Buy ", suffix=" in Neemuch | Vibe4You")
            is_casio = (
                clean(product.get("brand")).casefold() == "casio"
                and name.casefold().startswith("casio")
            )
            if is_casio:
                seo_name = re.sub(r"\s+-\s+", " ", name)
                if "watch" not in seo_name.casefold():
                    seo_name += " Watch"
                title = seo_title(seo_name, suffix=" Price in India | Vibe4You")
                description = clean(
                    f"Explore {seo_name} at Vibe4You. Check current price, "
                    "photos and availability. Outside Neemuch, request a "
                    "prepaid courier delivery quote before placing an order."
                )[:300]
            if not is_casio:
                # Restrict richer brand-first SEO titles to manufacturer fields
                # independently represented in known product listings. Never
                # equate a reseller or phone compatibility label to manufacturer.
                merchant_brand = clean(product.get("brand"))
                verified_seo_title_brands = {
                    "campus", "speed", "lavie", "minimalist",
                    "sebamed", "cetaphil", "himalaya", "kissan",
                    "mamaearth", "indulekha", "amul", "fortune",
                    "pantene", "pears", "zandu", "nivea",
                }
                seo_name = name
                if (
                    merchant_brand.casefold() in verified_seo_title_brands
                    and merchant_brand.casefold() not in name.casefold()
                ):
                    seo_name = f"{merchant_brand} {name}"
                if product.get("outsideNeemuchDeliveryAvailable") is True:
                    title = seo_title(seo_name, suffix=" - Price & Availability | Vibe4You")
                else:
                    title = seo_title(seo_name, prefix="Buy ", suffix=" in Neemuch | Vibe4You")
                seo_summary = clean(product.get("shortDescription"))
                # Uploaded supplier/import notes are not product features.
                if re.search(
                    r"\b(invoice|check original packaging|bulk upload|"
                    r"seller to confirm|price to confirm|sku to confirm|genuine .* product image|product image supplied)\b",
                    seo_summary, flags=re.IGNORECASE,
                ):
                    seo_summary = ""
                if seo_summary.casefold().startswith(name.casefold()):
                    seo_summary = seo_summary[len(name):].strip(" .,-")
                intro = f"Shop {seo_name} on Vibe4You in Neemuch."
                if seo_summary and len(seo_summary) >= 20:
                    intro += f" {seo_summary}"
                else:
                    category_label = clean(product.get("category"))
                    if category_label:
                        intro += f" Browse {category_label.lower()} from local shops."
                if product.get("outsideNeemuchDeliveryAvailable") is True:
                    suffix = (
                        "Check current price and availability. Outside Neemuch, "
                        "request a prepaid delivery quote before ordering."
                    )
                else:
                    suffix = (
                        "Check current price and availability. Delivery is "
                        "subject to serviceability within Neemuch."
                    )
                # Keep the accurate delivery-condition text visible even
                # when the product name or summary is unusually long.
                intro_budget = max(24, 300 - len(suffix) - 1)
                if len(intro) > intro_budget:
                    boundary = intro.rfind(". ", 0, intro_budget)
                    if boundary > max(40, intro_budget - 110):
                        intro = intro[:boundary + 1]
                    else:
                        intro = intro[:intro_budget - 2].rsplit(" ", 1)[0].rstrip(" .,-") + "."
                description = clean(f"{intro} {suffix}")[:300]
            is_lavie = (
                clean(product.get("brand")).casefold() == "lavie"
                and name.casefold().startswith("lavie ")
            )
            if is_lavie:
                # Brand-specific SEO based exclusively on existing model names,
                # first-party listing notes and published stock/colour options.
                # Do not imply unverified materials, GTINs, or colour-specific photos.
                lavie_features = {
                    "lavie lx glam bella 3c medium - smooth":
                        "Medium smooth-finish tote with top handles.",
                    "lavie lx glam bella 3c medium - textured":
                        "Medium tote with textured and patterned finish options.",
                    "lavie lx lucie emb trifold wallet - small":
                        "Small trifold wallet with an embroidered front flap.",
                    "lavie signature small bag":
                        "Small structured handbag with contrasting trim and top handles.",
                    "lavie lx mono26 box satchel - regular":
                        "Regular-size box satchel with geometric stitching and top handles.",
                    "lavie lx mono26 box satchel - medium":
                        "Medium box satchel with geometric stitching and top handles.",
                    "lavie lx fluf 25 frame handbag":
                        "Structured frame handbag with a top handle and shoulder strap.",
                    "lavie camelia 1c medium satchel bag":
                        "Medium structured satchel handbag.",
                    "lavie lx quare26 large satchel bag":
                        "Large satchel handbag with geometric front detailing.",
                    "lavie paris ales md flap sling bag":
                        "Medium flap sling bag with contrast panels.",
                    "lavie lx mono combo bag set":
                        "Coordinated bag set with photographed pieces.",
                    "lavie lx book dual h frame handbag":
                        "Structured frame handbag with top handles.",
                    "lavie luxe lx book sat frame handbag":
                        "Structured frame handbag with a framed silhouette.",
                }
                lavie_name = re.sub(r"\s+-\s+", " ", name)
                if not re.search(r"\b(bag|handbag|wallet)\b", lavie_name, re.IGNORECASE):
                    if "tote" in clean(product.get("shortDescription")).casefold():
                        lavie_name += " Tote Bag"
                    elif "satchel" in lavie_name.casefold():
                        lavie_name += " Bag"
                    else:
                        lavie_name += " Handbag"
                title = seo_title(lavie_name, suffix=" | Vibe4You")
                feature = lavie_features.get(name.casefold(), "")
                listed_colours = list(dict.fromkeys(
                    clean(variant.get("colourName"))
                    for variant in (product.get("variants") or [])
                    if isinstance(variant, dict) and clean(variant.get("colourName"))
                    and clean(variant.get("colourName")).casefold()
                    not in {"default", "standard", "as shown", "as pictured", "one size"}
                ))
                colours = (
                    " Colour options: " + ", ".join(listed_colours) + "."
                    if listed_colours else ""
                )
                if product.get("outsideNeemuchDeliveryAvailable") is True:
                    delivery = (
                        "Outside Neemuch, request a prepaid delivery quote "
                        "before ordering."
                    )
                else:
                    delivery = "Delivery is subject to serviceability within Neemuch."
                preface = clean(
                    f"Shop {lavie_name} on Vibe4You. {feature}{colours} "
                    "Check the current price and stock."
                )
                max_intro = max(70, 300 - len(delivery) - 1)
                if len(preface) > max_intro:
                    # Preserve the factual delivery condition and use whole words.
                    boundary = preface.rfind(". ", 0, max_intro)
                    if boundary > max_intro - 90:
                        preface = preface[:boundary + 1]
                    else:
                        preface = preface[:max_intro - 2].rsplit(" ", 1)[0].rstrip(" .,-") + "."
                description = clean(f"{preface} {delivery}")[:300]
            images = [
                absolute_url(value)
                for value in (product.get("images") or [])
                if absolute_url(value)
            ]
            if not images:
                thumbnail = absolute_url(product.get("thumbnail"))
                if thumbnail:
                    images = [thumbnail]
            variants = product.get("variants") or []
            in_stock = any(
                isinstance(variant.get("stock"), int) and variant.get("stock", 0) > 0
                for variant in variants
            )
            offer: dict[str, Any] = {
                "@type": "Offer",
                "url": canonical,
                "priceCurrency": "INR",
                "price": product.get("price"),
                "availability": "https://schema.org/InStock" if in_stock else "https://schema.org/OutOfStock",
                "itemCondition": "https://schema.org/NewCondition",
                "seller": {"@type": "Organization", "name": store_name},
            }
            product_schema: dict[str, Any] = {
                "@type": "Product",
                "@id": canonical + "#product",
                "name": name,
                "description": short_description or description,
                "url": canonical,
                "sku": clean(product.get("id")),
                "image": images,
                "offers": offer,
            }
            if is_casio:
                offer["seller"] = {
                    "@type": "Organization", "name": "Vibe4You", "url": origin,
                }
                product_schema["category"] = "Watches"
                product_schema["description"] = description
                verified_colors = {
                    clean(variant.get("colourName"))
                    for variant in variants
                    if clean(variant.get("colourName"))
                    and clean(variant.get("colourName")).casefold()
                    not in {"default", "as shown", "standard", "one size"}
                }
                if len(verified_colors) == 1:
                    color = next(iter(verified_colors))
                    if "/" not in color and "," not in color:
                        product_schema["color"] = color
            else:
                # This platform is the customer-facing merchant of record;
                # source shop metadata remains intact for internal attribution.
                offer["seller"] = {
                    "@type": "Organization", "name": "Vibe4You", "url": origin,
                }
                product_schema["description"] = description
                category = clean(product.get("category"))
                if category:
                    product_schema["category"] = category
                colors = {
                    clean(variant.get("colourName"))
                    for variant in variants
                    if clean(variant.get("colourName"))
                    and clean(variant.get("colourName")).casefold()
                    not in {"default", "as shown", "standard", "one size",
                            "assorted", "mixed", "as pictured", "non", "none", "n/a", "unknown", "not specified", "unspecified"}
                }
                if len(colors) == 1:
                    color = next(iter(colors))
                    if "/" not in color and "," not in color:
                        product_schema["color"] = color
            brand = "Casio" if is_casio else clean(product.get("brand"))
            if brand:
                product_schema["brand"] = {"@type": "Brand", "name": brand}
            if is_lavie:
                product_schema["description"] = description
                product_schema["category"] = (
                    "Wallets" if "wallet" in name.casefold() else "Handbags"
                )
            image = images[0] if images else ""
            structured_graph = [
                product_schema,
                {
                    "@type": "BreadcrumbList",
                    "itemListElement": [
                        {"@type": "ListItem", "position": 1, "name": "Vibe4You", "item": origin + "/"},
                        {"@type": "ListItem", "position": 2, "name": product.get("category") or "Products", "item": origin + "/products"},
                        {"@type": "ListItem", "position": 3, "name": name, "item": canonical},
                    ],
                },
            ]
            og_type = "product"
        elif kind == "page":
            spec = SPA_PAGE_SEO[url_path]
            title = spec["title"]
            description = spec["description"]
            heading = spec["heading"]
            image = ""
            neemuch_city = {
                "@type": "City",
                "name": "Neemuch",
                "address": {
                    "@type": "PostalAddress",
                    "addressLocality": "Neemuch",
                    "addressRegion": "Madhya Pradesh",
                    "addressCountry": "IN",
                },
            }
            if url_path == "/":
                structured_graph = [
                    {
                        "@type": "WebSite",
                        "@id": origin + "/#website",
                        "name": "Vibe4You",
                        "url": origin + "/",
                        "description": description,
                        "inLanguage": "en-IN",
                    },
                    {
                        "@type": "Organization",
                        "@id": origin + "/#organization",
                        "name": "Vibe4You",
                        "url": origin + "/",
                        "description": "Online marketplace for local shops in Neemuch, Madhya Pradesh.",
                        "areaServed": neemuch_city,
                        "sameAs": ["https://www.instagram.com/vibe44you"],
                    },
                ]
            else:
                page_name = heading
                page_schema = {
                    "@type": spec.get("schema_type", "CollectionPage"),
                    "@id": canonical + "#page",
                    "url": canonical,
                    "name": page_name,
                    "description": description,
                    "isPartOf": {"@type": "WebSite", "@id": origin + "/#website", "name": "Vibe4You", "url": origin + "/"},
                }
                if page_schema["@type"] == "CollectionPage":
                    page_schema["about"] = neemuch_city
                structured_graph = [
                    page_schema,
                    {
                        "@type": "BreadcrumbList",
                        "itemListElement": [
                            {"@type": "ListItem", "position": 1, "name": "Vibe4You", "item": origin + "/"},
                            {"@type": "ListItem", "position": 2, "name": page_name, "item": canonical},
                        ],
                    },
                ]
            og_type = "website"
        else:
            store = entity
            name = clean(store.get("storeName")) or "Local Store"
            heading = name
            store_description = clean(store.get("description"))
            address_text = clean(store.get("address"))
            city = clean(store.get("city")) or "Neemuch"
            description = clean(
                f"{name} in Neemuch on Vibe4You. {store_description}"
            )[:300]
            title = f"Shop at {name} in Neemuch | Vibe4You"
            image = absolute_url(store.get("logoImage") or store.get("bannerImage"))
            store_schema: dict[str, Any] = {
                "@type": "Store",
                "@id": canonical + "#store",
                "name": name,
                "url": canonical,
                "description": store_description or description,
                "address": {
                    "@type": "PostalAddress",
                    "streetAddress": address_text,
                    "addressLocality": city,
                    "addressRegion": "Madhya Pradesh",
                    "postalCode": clean(store.get("pincode")),
                    "addressCountry": "IN",
                },
            }
            if image:
                store_schema["image"] = image
            structured_graph = [
                store_schema,
                {
                    "@type": "BreadcrumbList",
                    "itemListElement": [
                        {"@type": "ListItem", "position": 1, "name": "Vibe4You", "item": origin + "/"},
                        {"@type": "ListItem", "position": 2, "name": "Local Stores", "item": origin + "/stores"},
                        {"@type": "ListItem", "position": 3, "name": name, "item": canonical},
                    ],
                },
            ]
            try:
                listed = [
                    item for item in self._shops().list_store_published_products(store["id"])
                    if item.get("active") is True and item.get("slug")
                ]
                if listed:
                    kinds: list[str] = []
                    for item in listed:
                        label = clean(item.get("subcategory")) or clean(item.get("category"))
                        if label and label not in kinds:
                            kinds.append(label)
                    description = clean(
                        f"{name} in Neemuch on Vibe4You. "
                        f"Shop {', '.join(kinds[:4])} online - {len(listed)} products. "
                        f"{store_description}"
                    )[:300]
                    structured_graph.append(
                        {
                            "@type": "ItemList",
                            "name": f"Products from {name}",
                            "numberOfItems": len(listed),
                            "itemListElement": [
                                {
                                    "@type": "ListItem",
                                    "position": index + 1,
                                    "url": origin + "/product/" + str(item["slug"]),
                                    "name": clean(item.get("name")),
                                }
                                for index, item in enumerate(listed[:12])
                            ],
                        }
                    )
            except Exception:
                pass
            og_type = "website"

        structured = {"@context": "https://schema.org", "@graph": structured_graph}
        structured_json = (
            json.dumps(structured, separators=(",", ":"), ensure_ascii=False)
            .replace("&", "\\u0026")
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
        )

        html = re.sub(r"<title>.*?</title>", f"<title>{html_attr(title)}</title>", html, count=1, flags=re.DOTALL)
        html = re.sub(
            r'<meta name="description" content="[^"]*"\s*/?>',
            f'<meta name="description" content="{html_attr(description)}" />',
            html,
            count=1,
        )
        html = re.sub(
            r'<link rel="canonical" href="[^"]*"\s*/?>',
            f'<link rel="canonical" href="{html_attr(canonical)}" />',
            html,
            count=1,
        )
        html = re.sub(
            r'<meta property="og:type" content="[^"]*"\s*/?>',
            f'<meta property="og:type" content="{og_type}" />',
            html,
            count=1,
        )
        html = re.sub(
            r'<meta property="og:title" content="[^"]*"\s*/?>',
            f'<meta property="og:title" content="{html_attr(title)}" />',
            html,
            count=1,
        )
        html = re.sub(
            r'<meta property="og:description" content="[^"]*"\s*/?>',
            f'<meta property="og:description" content="{html_attr(description)}" />',
            html,
            count=1,
        )
        html = re.sub(
            r'<meta property="og:url" content="[^"]*"\s*/?>',
            f'<meta property="og:url" content="{html_attr(canonical)}" />',
            html,
            count=1,
        )
        if image:
            if re.search(r'<meta property="og:image" content="[^"]*"\s*/?>', html):
                html = re.sub(
                    r'<meta property="og:image" content="[^"]*"\s*/?>',
                    f'<meta property="og:image" content="{html_attr(image)}" />',
                    html,
                    count=1,
                )
            else:
                html = html.replace(
                    "</head>",
                    f'<meta property="og:image" content="{html_attr(image)}" />\n  </head>',
                    1,
                )
        html = html.replace(
            "</head>",
            f'<script type="application/ld+json">{structured_json}</script>\n  </head>',
            1,
        )
        html = html.replace(
            '<div id="root"></div>',
            '<div id="root"><main data-v4y-seo-shell="true">'
            f'<h1>{html_attr(heading)}</h1></main></div>',
            1,
        )
        return html.encode("utf-8")

    def send_head(self):  # noqa: N802 - stdlib override name
        url_path = urlsplit(self.path).path
        self._seo_request_product = None
        if self._sensitive_path(url_path):
            self.send_error(HTTPStatus.NOT_FOUND)
            return None
        # V4Y-054: Google Play privacy and account-deletion addresses.
        if url_path in ("/privacy-policy", "/delete-account"):
            self.send_response(HTTPStatus.MOVED_PERMANENTLY)
            self.send_header(
                "Location", "/privacy" if url_path == "/privacy-policy" else "/account-deletion"
            )
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        if url_path == "/account-deletion":
            self.path = "/account-deletion.html"
            return super().send_head()
        translated = Path(self.translate_path(url_path))
        if url_path == "/":
            home_body = self._spa_seo_shell_body(url_path)
            if home_body is not None:
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(home_body)))
                self.send_header("Cache-Control", "public, max-age=300")
                self.end_headers()
                return io.BytesIO(home_body)
        if not translated.exists() and "." not in Path(url_path).name and not url_path.startswith(API_PREFIX):
            try:
                seo_body = self._spa_seo_shell_body(url_path)
            except Exception:
                if url_path.startswith(("/product/", "/store/")):
                    return self._seo_temporarily_unavailable()
                raise
            if seo_body is not None:
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(seo_body)))
                self.send_header("Cache-Control", "public, max-age=300")
                self.end_headers()
                return io.BytesIO(seo_body)
            try:
                if self._spa_route_missing(url_path):
                    return self._send_spa_not_found()
            except Exception:
                return self._seo_temporarily_unavailable()
            self.path = "/index.html"
        return super().send_head()

    def _seo_public_product(self, slug: str) -> dict[str, Any] | None:
        # Cache only within this request; every new request rechecks publication.
        cached = getattr(self, "_seo_request_product", None)
        if cached is not None and cached[0] == slug:
            return cached[1]
        try:
            product = self._shops().get_published_product(slug)
        except SecurityError as error:
            if error.status != HTTPStatus.NOT_FOUND or error.code != "product_not_found":
                raise
            product = None
        self._seo_request_product = (slug, product)
        return product

    def _seo_public_store(self, slug: str) -> dict[str, Any] | None:
        cls = type(self)
        with cls.seo_store_lock:
            if time.monotonic() >= cls.seo_store_expires:
                try:
                    stores = self._shops().list_active_stores(limit=200)
                    if len(stores) > 200:
                        raise RuntimeError("Unexpected active store limit.")
                    refreshed = {store["slug"]: store for store in stores}
                except Exception:
                    cls.seo_store_cache = {}
                    cls.seo_store_failed = True
                    cls.seo_store_expires = time.monotonic() + 1.0
                    raise
                cls.seo_store_cache = refreshed
                cls.seo_store_failed = False
                cls.seo_store_expires = time.monotonic() + 5.0
            if cls.seo_store_failed:
                raise RuntimeError("Active store lookup temporarily unavailable.")
            return cls.seo_store_cache.get(slug)

    def _seo_temporarily_unavailable(self):
        body = b"<!doctype html><html><head><title>Temporarily unavailable</title></head><body>Please try again shortly.</body></html>"
        self.send_response(HTTPStatus.SERVICE_UNAVAILABLE)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Retry-After", "60")
        self.end_headers()
        return io.BytesIO(body)

    def _catalog_route_missing(self, url_path: str) -> bool:
        if url_path in ("/product", "/product/", "/store", "/store/"):
            return True
        if url_path.startswith("/neemuch/"):
            return url_path not in NEEMUCH_LOCAL_PAGES
        if not url_path.startswith(("/product/", "/store/")):
            return False
        prefix = "/product/" if url_path.startswith("/product/") else "/store/"
        slug = unquote(url_path[len(prefix):]).strip().rstrip("/")
        if not slug or "/" in slug or len(slug) > 128:
            return True
        if prefix == "/store/":
            return self._seo_public_store(slug) is None
        if self._seo_public_product(slug) is not None:
            return False
        # Preserve the existing static-catalogue SPA fallback, active entries only.
        products = self.payment_service.product_snapshot()
        return not any(
            products.get(product_id, {}).get("active") is True
            and (product_id == slug or products[product_id].get("slug") == slug)
            for product_id in self.payment_service._static_products
        )

    def _spa_route_missing(self, url_path: str) -> bool:
        normalized = url_path if url_path == "/" else url_path.rstrip("/")
        if normalized in SPA_EXACT_ROUTES:
            return False
        if any(pattern.fullmatch(normalized) for pattern in SPA_DYNAMIC_ROUTE_PATTERNS):
            return False
        if normalized.startswith(("/product/", "/store/", "/neemuch/")):
            return self._catalog_route_missing(normalized)
        return True

    def _send_spa_not_found(self):
        try:
            body = Path(self.translate_path("/index.html")).read_bytes()
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return None
        self.send_response(HTTPStatus.NOT_FOUND)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Robots-Tag", "noindex")
        self.end_headers()
        return io.BytesIO(body)

    @staticmethod
    def _sensitive_path(path: str) -> bool:
        decoded = unquote(path).replace("\\", "/")
        lowered = ("/" + posixpath.normpath(decoded).lstrip("/")).casefold()
        return (
            lowered in ("/backups", "/logs")
            or lowered.startswith(("/backups/", "/logs/", "/.config/", "/admin", "/api/admin/", "/api/internal-admin/", "/admin-api/"))
            or lowered.startswith(("/tools/", "/payment-data/"))
            or lowered in ("/.env", "/secrets.env", "/styledash.db", "/firebase-service-account.json", "/serve.py", "/styledash_security.py")
            or lowered.endswith((".db", ".db-wal", ".db-shm", ".log", ".py", ".pyc"))
        )

    def log_message(self, format: str, *args: Any) -> None:
        # Request bodies and environment configuration are never logged. Redact
        # token-shaped query parameters as defense in depth for stale/manual URLs.
        redacted = tuple(
            ACCESS_LOG_TOKEN_PATTERN.sub(r"\1[redacted]", value)
            if isinstance(value, str)
            else value
            for value in args
        )
        super().log_message(format, *redacted)


def _default_payment_file(filename: str) -> Path:
    script = Path(__file__).resolve()
    candidates = (
        script.parent / "payment-data" / filename,
        script.parent.parent / "server" / "payment-data" / filename,
    )
    return next((candidate for candidate in candidates if candidate.exists()), candidates[-1])


def create_server(
    bind: str,
    port: int,
    directory: Path,
    catalog_path: Path,
    settings_path: Path,
    data_directory: Path,
    *,
    service: PaymentService | None = None,
) -> ThreadingHTTPServer:
    delivery_queue: PasswordResetDeliveryQueue | None = None
    registration_delivery_queue: PasswordResetDeliveryQueue | None = None
    registration_verifier: PendingEmailRegistration | None = None
    if service is None:
        encryption_key = os.environ.get("STYLEDASH_TOTP_ENCRYPTION_KEY", "").strip()
        if not encryption_key:
            raise RuntimeError("STYLEDASH_TOTP_ENCRYPTION_KEY is required")
        database_path = Path(
            os.environ.get("STYLEDASH_DATABASE_PATH", str(data_directory.parent / "styledash.db"))
        ).resolve()
        mailer = SmtpPasswordResetSender.from_environment()
        delivery_queue = PasswordResetDeliveryQueue(mailer) if mailer is not None else None
        security_store = SecurityStore(
            database_path,
            encryption_key,
            password_reset_dispatcher=delivery_queue.dispatch if delivery_queue is not None else None,
        )
        registration_delivery_queue = (
            PasswordResetDeliveryQueue(SmtpRegistrationSender(mailer))
            if mailer is not None else None
        )
        registration_verifier = PendingEmailRegistration(
            security_store, registration_delivery_queue.dispatch if registration_delivery_queue else None
        )
        payment_service = PaymentService(
            catalog_path, settings_path, data_directory, security_store=security_store
        )
    else:
        payment_service = service
    class BoundStyleDashRequestHandler(StyleDashRequestHandler):
        pass

    data_root = data_directory.parent if data_directory.name == "runtime" else data_directory
    product_image_directory = (data_root / "product-images").resolve()
    product_image_directory.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(product_image_directory, 0o700)
    except OSError:
        pass
    BoundStyleDashRequestHandler.payment_service = payment_service
    BoundStyleDashRequestHandler.registration_verifier = registration_verifier
    BoundStyleDashRequestHandler.product_image_directory = product_image_directory
    BoundStyleDashRequestHandler.review_workflow = (
        ReviewWorkflow(payment_service.security.path) if payment_service.security is not None else None
    )
    BoundStyleDashRequestHandler.rate_limiter = RateLimiter()
    BoundStyleDashRequestHandler.seo_store_lock = threading.Lock()
    BoundStyleDashRequestHandler.seo_store_cache = {}
    BoundStyleDashRequestHandler.seo_store_expires = 0.0
    BoundStyleDashRequestHandler.seo_store_failed = False
    handler = partial(BoundStyleDashRequestHandler, directory=str(directory))
    server = ThreadingHTTPServer((bind, port), handler)
    if service is None and (delivery_queue is not None or registration_delivery_queue is not None):
        original_server_close = server.server_close

        def close_server() -> None:
            if delivery_queue is not None:
                delivery_queue.close()
            if registration_delivery_queue is not None:
                registration_delivery_queue.close()
            original_server_close()

        server.server_close = close_server  # type: ignore[method-assign]
    return server


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--directory", default=".")
    parser.add_argument(
        "--catalog",
        default=os.environ.get("STYLEDASH_CATALOG_PATH", str(_default_payment_file("catalog.json"))),
    )
    parser.add_argument(
        "--settings",
        default=os.environ.get("STYLEDASH_SETTINGS_PATH", str(_default_payment_file("settings.json"))),
    )
    parser.add_argument(
        "--data-directory",
        default=os.environ.get("STYLEDASH_DATA_DIR", str(Path.home() / ".local" / "share" / "styledash")),
    )
    args = parser.parse_args()

    directory = Path(args.directory).resolve()
    server = create_server(
        args.bind,
        args.port,
        directory,
        Path(args.catalog).resolve(),
        Path(args.settings).resolve(),
        Path(args.data_directory).resolve(),
    )
    print(f"Serving Vibe4You at http://{args.bind}:{args.port}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
