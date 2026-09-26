import unittest

from scripts.catalog_normalization import (
    PRODUCT_CATEGORIES,
    build_product_tags,
    normalize_brand,
    normalize_delivery_type,
    normalize_department,
    normalize_product_category,
    normalize_size_label,
    normalize_subcategory,
)
from scripts.store_categories import STORE_CATEGORIES
from scripts.styledash_security import SecurityError
from scripts.styledash_shops import ALLOWED_CATEGORIES


class CatalogNormalizationTests(unittest.TestCase):
    def test_department_aliases_are_canonical(self) -> None:
        self.assertEqual(
            normalize_department('Mens', name='Casual Shirt', description='Everyday shirt', category='Clothing & Fashion'),
            'men',
        )
        self.assertEqual(
            normalize_department('female', name='Cotton Kurta', description='Women kurta', category='Clothing & Fashion'),
            'women',
        )
        self.assertEqual(
            normalize_department('boys', name='Printed Sneakers', description='Kids footwear', category='Footwear'),
            'kids',
        )

    def test_legacy_merchandise_class_is_not_accepted_as_new_department(self) -> None:
        with self.assertRaises(SecurityError):
            normalize_department(
                'footwear',
                name='Premium Everyday Sneakers',
                description='Comfortable casual sneakers',
                category='Footwear',
            )

    def test_accessory_and_footwear_categories_are_inferred(self) -> None:
        self.assertEqual(
            normalize_product_category(
                'Clothing & Fashion',
                name='Kundan Jhumka Earring',
                description='Kundan stone earring',
            ),
            'Accessories',
        )
        self.assertEqual(
            normalize_product_category(
                'Clothing & Fashion',
                name='Skechers Slider',
                description='Lightweight slider',
            ),
            'Footwear',
        )

    def test_beauty_category_is_inferred_without_misclassifying_as_accessories(self) -> None:
        self.assertEqual(
            normalize_product_category(
                'Accessories',
                name='Premium Rose Perfume',
                description='Long lasting fragrance for daily use',
            ),
            'Beauty & Personal Care',
        )
        self.assertEqual(
            normalize_product_category(
                'Clothing & Fashion',
                name='Vitamin C Face Wash',
                description='Skin care cleanser',
            ),
            'Beauty & Personal Care',
        )
        self.assertEqual(
            normalize_subcategory(None, name='Premium Rose Perfume', category='Beauty & Personal Care'),
            'Perfume',
        )
        self.assertEqual(
            normalize_product_category(
                'Accessories',
                name='Rose Gold Bangles',
                description='Fashion jewellery bangles',
            ),
            'Accessories',
        )

    def test_live_category_sets_and_gift_home_normalization(self) -> None:
        expected = {
            'Clothing & Fashion',
            'Footwear',
            'Accessories',
            'Beauty & Personal Care',
            'Electronics',
            'Gifts',
            'Home & Living',
        }
        self.assertEqual(PRODUCT_CATEGORIES, expected)
        self.assertEqual(ALLOWED_CATEGORIES, expected)
        self.assertEqual(set(STORE_CATEGORIES), expected)
        self.assertNotIn('General Store', PRODUCT_CATEGORIES)
        self.assertNotIn('General Store', ALLOWED_CATEGORIES)
        self.assertEqual(
            normalize_product_category(
                'Clothing & Fashion',
                name='Festive Gift Hamper',
                description='Gift box with greeting card',
            ),
            'Gifts',
        )
        self.assertEqual(
            normalize_subcategory(None, name='Festive Gift Hamper', category='Gifts'),
            'Gift Hampers',
        )
        self.assertEqual(
            normalize_product_category(
                'Clothing & Fashion',
                name='Kitchen Storage Organiser',
                description='Home living household storage',
            ),
            'Home & Living',
        )
        self.assertEqual(
            normalize_subcategory(
                None,
                name='Kitchen Storage Organiser',
                category='Home & Living',
            ),
            'Kitchen & Dining',
        )

    def test_known_brand_is_inferred_only_when_deterministic(self) -> None:
        self.assertEqual(normalize_brand(None, name='Puma Slider'), 'Puma')
        self.assertEqual(normalize_brand('skechers', name='Comfort Slider'), 'Skechers')
        self.assertIsNone(normalize_brand(None, name='Premium Everyday Sneakers'))

    def test_sizes_are_canonicalized_by_category(self) -> None:
        self.assertEqual(normalize_size_label('8', 'Footwear'), 'UK 8')
        self.assertEqual(normalize_size_label('uk-8', 'Footwear'), 'UK 8')
        self.assertEqual(normalize_size_label('42', 'Footwear'), 'EU 42')
        self.assertEqual(normalize_size_label('free size', 'Accessories'), 'One Size')
        self.assertEqual(normalize_size_label('m', 'Clothing & Fashion'), 'M')

    def test_subcategory_and_delivery_are_normalized(self) -> None:
        self.assertEqual(
            normalize_subcategory(None, name='Multi Color Mini Jhumka', category='Accessories'),
            'Earrings',
        )
        self.assertEqual(
            normalize_subcategory(None, name='Puma Slider', category='Footwear'),
            'Sliders',
        )
        self.assertEqual(normalize_delivery_type('Weekend Express'), 'express')
        self.assertEqual(normalize_delivery_type(None), 'normal')
        with self.assertRaises(SecurityError):
            normalize_delivery_type('super-fast')

    def test_live_subcategory_aliases_are_canonicalized(self) -> None:
        aliases = {
            'Sneaker': 'Sneakers',
            'Sport Shoes': 'Sports Shoes',
            'FlipFlop': 'Slippers & Flip-Flops',
            'Sleepers': 'Slippers & Flip-Flops',
            'Slides': 'Sliders',
            'Watch2': 'Watches',
            'Accesories': 'Accessories',
            'Skincare': 'Skin Care',
        }
        for source, expected in aliases.items():
            with self.subTest(source=source):
                self.assertEqual(
                    normalize_subcategory(source, name='Catalogue Product', category='Footwear'),
                    expected,
                )

    def test_missing_subcategories_are_inferred_for_supported_categories(self) -> None:
        self.assertEqual(
            normalize_subcategory(None, name='Classic Cotton Shirt', category='Clothing & Fashion'),
            'Shirts',
        )
        self.assertEqual(
            normalize_subcategory(None, name='Rose Gold Watch', category='Accessories'),
            'Watches',
        )
        self.assertEqual(
            normalize_subcategory(None, name='Wireless Earbuds', category='Electronics'),
            'Audio',
        )

    def test_public_product_tags_are_useful_bounded_and_deduplicated(self) -> None:
        tags = build_product_tags(
            name='Puma Slider for Men',
            brand='Puma',
            store_name='Goutam Shoes',
            department='men',
            category='Footwear',
            subcategory='Sliders',
        )
        self.assertIn('local-shop', tags)
        self.assertIn('puma slider for men', tags)
        self.assertIn('goutam shoes', tags)
        self.assertIn('footwear', tags)
        self.assertIn('sliders', tags)
        self.assertIn('slides', tags)
        self.assertEqual(len(tags), len(set(tags)))
        self.assertLessEqual(len(tags), 24)


if __name__ == '__main__':
    unittest.main()
