import unittest

from scripts.catalog_normalization import (
    normalize_brand,
    normalize_delivery_type,
    normalize_department,
    normalize_product_category,
    normalize_size_label,
    normalize_subcategory,
)
from scripts.styledash_security import SecurityError


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


if __name__ == '__main__':
    unittest.main()
