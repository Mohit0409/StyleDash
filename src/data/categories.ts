export interface CategoryItem {
  id: string;
  name: string;
  slug: string;
  department: string;
  icon?: string;
  subcategories: string[];
}

export const CATEGORIES: CategoryItem[] = [
  // Men
  { id: 'm-tshirts', name: 'T-Shirts', slug: 'men-tshirts', department: 'men', subcategories: ['Oversized', 'Polo', 'Graphic', 'Solid', 'V-Neck'] },
  { id: 'm-shirts', name: 'Shirts', slug: 'men-shirts', department: 'men', subcategories: ['Casual', 'Formal', 'Linen', 'Denim', 'Printed'] },
  { id: 'm-jeans', name: 'Jeans', slug: 'men-jeans', department: 'men', subcategories: ['Slim Fit', 'Regular Fit', 'Relaxed Fit', 'Cargo'] },
  { id: 'm-trousers', name: 'Trousers', slug: 'men-trousers', department: 'men', subcategories: ['Chinos', 'Formal Trousers', 'Joggers'] },
  { id: 'm-hoodies', name: 'Hoodies & Jackets', slug: 'men-hoodies-jackets', department: 'men', subcategories: ['Hoodies', 'Sweatshirts', 'Denim Jackets', 'Bomber Jackets'] },
  { id: 'm-ethnic', name: 'Ethnic Wear', slug: 'men-ethnic', department: 'men', subcategories: ['Kurtas', 'Nehru Jackets', 'Kurta Sets'] },
  { id: 'm-active', name: 'Activewear', slug: 'men-activewear', department: 'men', subcategories: ['Gym Tees', 'Track Pants', 'Shorts'] },
  { id: 'm-inner', name: 'Innerwear & Essentials', slug: 'men-innerwear', department: 'men', subcategories: ['Briefs', 'Boxers', 'Socks', 'Vests'] },

  // Women
  { id: 'w-dresses', name: 'Dresses', slug: 'women-dresses', department: 'women', subcategories: ['Maxi', 'Midi', 'Bodycon', 'A-Line', 'Floral'] },
  { id: 'w-tops', name: 'Tops & Tees', slug: 'women-tops', department: 'women', subcategories: ['Crop Tops', 'Blouses', 'T-Shirts', 'Shirts'] },
  { id: 'w-jeans', name: 'Jeans & Jeggings', slug: 'women-jeans', department: 'women', subcategories: ['High Rise', 'Wide Leg', 'Skinny', 'Mom Jeans'] },
  { id: 'w-kurtas', name: 'Kurtas & Suits', slug: 'women-kurtas', department: 'women', subcategories: ['Anarkali', 'Straight Kurta', 'Kurta Sets'] },
  { id: 'w-sarees', name: 'Sarees', slug: 'women-sarees', department: 'women', subcategories: ['Silk', 'Cotton', 'Georgette', 'Chiffon'] },
  { id: 'w-coords', name: 'Co-ord Sets', slug: 'women-coords', department: 'women', subcategories: ['Casual Sets', 'Party Sets', 'Lounge Sets'] },
  { id: 'w-active', name: 'Activewear', slug: 'women-activewear', department: 'women', subcategories: ['Sports Bras', 'Leggings', 'Workout Tops'] },
  { id: 'w-inner', name: 'Innerwear & Essentials', slug: 'women-innerwear', department: 'women', subcategories: ['Lingerie', 'Sleepwear', 'Socks'] },

  // Kids
  { id: 'k-boys', name: 'Boys Clothing', slug: 'kids-boys', department: 'kids', subcategories: ['T-Shirts', 'Shirts', 'Shorts', 'Jeans'] },
  { id: 'k-girls', name: 'Girls Clothing', slug: 'kids-girls', department: 'kids', subcategories: ['Frocks', 'Tops', 'Skirts', 'Leggings'] },
  { id: 'k-infants', name: 'Infants & Toddlers', slug: 'kids-infants', department: 'kids', subcategories: ['Onesies', 'Rompers', 'Sets'] },
  { id: 'k-school', name: 'School Essentials', slug: 'kids-school', department: 'kids', subcategories: ['Backpacks', 'Uniform Extras', 'Socks'] },

  // Footwear
  { id: 'f-sneakers', name: 'Sneakers', slug: 'footwear-sneakers', department: 'footwear', subcategories: ['Casual Sneakers', 'High Tops', 'Running Shoes'] },
  { id: 'f-casual', name: 'Casual & Formals', slug: 'footwear-casual', department: 'footwear', subcategories: ['Loafers', 'Oxford Shoes', 'Derby'] },
  { id: 'f-sandals', name: 'Sandals & Slides', slug: 'footwear-sandals', department: 'footwear', subcategories: ['Floaters', 'Slides', 'Flip-Flops', 'Heels'] },

  // Accessories
  { id: 'a-bags', name: 'Bags & Backpacks', slug: 'accessories-bags', department: 'accessories', subcategories: ['Handbags', 'Totes', 'Backpacks', 'Wallets'] },
  { id: 'a-watches', name: 'Watches', slug: 'accessories-watches', department: 'accessories', subcategories: ['Analog', 'Smartwatches', 'Chronograph'] },
  { id: 'a-jewellery', name: 'Fashion Jewellery', slug: 'accessories-jewellery', department: 'accessories', subcategories: ['Earrings', 'Necklaces', 'Bracelets'] },
  { id: 'a-extras', name: 'Caps, Belts & Sunglasses', slug: 'accessories-extras', department: 'accessories', subcategories: ['Caps', 'Belts', 'Sunglasses', 'Scarves'] }
];
