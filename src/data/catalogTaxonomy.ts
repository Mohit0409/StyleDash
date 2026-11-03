/** Shared product/store taxonomy used by all customer and owner category selectors.
 * Existing category labels are preserved so historical products remain filterable.
 * Subcategories are suggestions, never destructive migrations of legacy values.
 */
export const PRODUCT_CATEGORY_TAXONOMY = [
  { name: 'Clothing & Fashion', subcategories: ['T-Shirts', 'Shirts', 'Jeans', 'Trousers', 'Kurta Sets', 'Anarkali Sets', 'Sports Bra', 'Kids Nightwear & Co-ord Sets', 'Kurtas & Kurtis', 'Sarees', 'Blouses', 'Petticoats', 'Dresses', 'Tops', 'Co-ord Sets', 'Innerwear', 'Activewear', 'Kids Clothing'] },
  { name: 'Footwear', subcategories: ['Sports Shoes', 'Running Shoes', 'Sneakers', 'Women\'s Footwear', 'Flats', 'Loafers', 'Walkers', 'Casual Shoes', 'Formal Shoes', 'Sandals', 'Slippers & Flip-Flops', 'Sliders', 'Clogs & Crocs', 'Heels', 'School Shoes'] },
  { name: 'Accessories', subcategories: ['Watches', 'Analog Watches', 'Digital Watches', 'Handkerchiefs', 'Bracelets', 'Clutch Bags', 'Decorative Lace', 'Smart Watches', 'Fashion Jewellery', 'Earrings', 'Necklaces', 'Bangles', 'Rings', 'Handbags', 'Tote Bags', 'Backpacks', 'Wallets', 'Belts', 'Hair Accessories', 'Sunglasses'] },
  { name: 'Beauty & Personal Care', subcategories: ['Skin Care', 'Face Wash', 'Face Cream', 'Hair Shampoos', 'Hair Conditioner', 'Soaps & Body washes', 'Creams & Moisturizers', 'Body Lotion', 'Body Spray', 'Body Wash', 'Hair Oil', 'Hair Care', 'Shampoo', 'Conditioner', 'Perfume', 'Deodorant', 'Makeup', 'Feminine Care', 'Oral Care', 'Bath & Body', 'Grooming'] },
  { name: 'Electronics', subcategories: ['Mobile Phones', 'Mobile Accessories', 'Power Tools & Accessories', 'Personal Care Appliances', 'Chargers', 'Power Banks', 'Audio Accessories', 'Smart Devices', 'Electrical Accessories', 'Home Electronics'] },
  { name: 'Gifts', subcategories: ['Gift Hampers', 'Gift Sets', 'Gift Box', 'Decorative Roses', 'Greeting Cards', 'Personalised Gifts', 'Decorative Gifts', 'Soft Toys'] },
  { name: 'Groceries', subcategories: ['Rice & Grains', 'Flour & Atta', 'Pulses & Dals', 'Oil & Ghee', 'Sugar & Salt', 'Spices', 'Tea & Coffee', 'Breakfast Cereals', 'Jams & Honey', 'Snacks', 'Beverages', 'Detergents & Cleaning'] },
  { name: 'Home & Living', subcategories: ['Bedsheets & Covers', 'Bath Linens', 'Bathroom Fittings', 'Electrical Lighting', 'Plumbing Supplies', 'Towels', 'Kitchenware', 'Cookware', 'Home Appliances', 'Juicers & Mixers', 'Home Decor', 'Storage & Organisers', 'Household Essentials'] },
  { name: 'Health & Pharmacy', subcategories: ['Health & Personal Care', 'First Aid', 'OTC Medicines', 'Medical Devices', 'Wellness Essentials', 'Hygiene', 'Pharmacy Products'] },
  { name: 'Health & Nutrition', subcategories: [] },
  { name: 'Baby Care', subcategories: ['Baby Food', 'Infant Formula', 'Baby Skin Care', 'Diapers & Wipes', 'Feeding Accessories', 'Baby Clothing', 'Baby Bath'] },
  { name: 'Pet Supplies', subcategories: ['Dog Food', 'Cat Food', 'Pet Treats', 'Pet Grooming', 'Pet Accessories', 'Pet Toys', 'Pet Health'] },
  { name: 'Mobile Accessories', subcategories: ['Phone Back Covers', 'Transparent Back Covers', 'Tempered Glass', 'Camera Lens Protectors', 'Phone Chargers', 'Wireless Chargers', 'Cables', 'Phone Stands', 'Earphones'] },
  { name: 'Automotive Accessories', subcategories: ['Car Dashboard Accessories', 'Car Chargers', 'Car Phone Holders', 'Car Cleaning', 'Car Fragrances', 'Two-Wheeler Accessories'] },
  { name: 'Toys & Games', subcategories: ['Remote Control Toys', 'Board Games', 'Outdoor Toys', 'Educational Toys', 'Soft Toys', 'Action Figures'] },
  { name: 'Stationery & Books', subcategories: ['Notebooks', 'Pens & Pencils', 'Office Supplies', 'School Supplies', 'Books', 'Art & Craft'] },
  { name: 'Sports & Fitness', subcategories: ['Fitness Accessories', 'Massage & Recovery', 'Sports Equipment', 'Yoga Accessories', 'Gym Accessories', 'Outdoor Gear'] },
  { name: 'Hardware & Tools', subcategories: ['Plumbing & Fittings', 'Bathroom Fittings', 'Electrical Supplies', 'Hand Tools', 'Power Tools', 'Fasteners & Adhesives', 'Tapes & Sealants', 'Utility Hardware'] },
  { name: 'General Store', subcategories: ['Daily Essentials', 'Household Supplies', 'Assorted Products', 'Utility Items'] },
] as const;

export const PRODUCT_CATEGORIES: string[] = PRODUCT_CATEGORY_TAXONOMY.map(category => category.name);
export const STORE_CATEGORIES: string[] = [...PRODUCT_CATEGORIES];
export const getCategorySubcategories = (category: string): string[] =>
  [...(PRODUCT_CATEGORY_TAXONOMY.find(item => item.name === category)?.subcategories || [])];
