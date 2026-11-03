export interface NeemuchShoppingPageConfig {
  slug: string;
  label: string;
  title: string;
  description: string;
  heading: string;
  intro: string;
  category?: string;
  department?: string;
  subcategories?: string[];
  nameTerms?: string[];
  allProducts?: boolean;
  catalogueUrl?: string;
  directory?: 'stores';
}

export const NEEMUCH_SHOPPING_PAGES: NeemuchShoppingPageConfig[] = [
  {
    slug: 'shoes',
    label: 'Shoes in Neemuch',
    title: 'Buy Shoes in Neemuch | Sneakers, Sports Shoes & Footwear | Vibe4You',
    description: 'Shop shoes in Neemuch from local stores on Vibe4You. Browse sneakers, sports shoes, sliders, sandals and more with Same Day Delivery in the supported Neemuch area.',
    heading: 'Buy Shoes in Neemuch',
    intro: 'Looking for good shoes in Neemuch? Compare footwear from local Neemuch stores in one place, including sneakers, sports shoes, sliders, sandals, loafers and everyday footwear.',
    category: 'Footwear',
  },
  {
    slug: 'clothes',
    label: 'Clothes in Neemuch',
    title: 'Shop Clothes in Neemuch | Men, Women & Kids Fashion | Vibe4You',
    description: 'Buy clothes in Neemuch online from local shops. Discover T-shirts, shirts, jeans, tops, kurtas and more with Same Day Delivery across the supported Neemuch service area.',
    heading: 'Shop Clothes in Neemuch',
    intro: 'Find clothes from local Neemuch shops without visiting multiple stores. Browse men’s, women’s and kids fashion, compare styles and prices, and order locally through Vibe4You.',
    category: 'Clothing & Fashion',
  },
  {
    slug: 'mens-clothing',
    label: "Men's Clothing",
    title: "Men's Clothing in Neemuch | T-Shirts, Shirts & Jeans | Vibe4You",
    description: "Shop men's clothing in Neemuch from local stores. Browse T-shirts, shirts, jeans and more with convenient local ordering and Same Day Delivery in supported areas.",
    heading: "Men's Clothing in Neemuch",
    intro: "Browse men’s fashion available from local Neemuch sellers, including T-shirts, shirts, jeans and everyday styles. Vibe4You brings local store inventory together in one searchable catalogue.",
    category: 'Clothing & Fashion',
    department: 'men',
  },
  {
    slug: 'womens-clothing',
    label: "Women's Clothing",
    title: "Women's Clothing in Neemuch | Tops, Jeans, Kurtas & More | Vibe4You",
    description: "Shop women's clothing in Neemuch from local boutiques and stores. Browse tops, jeans, kurtas, sets and more with Same Day Delivery in supported Neemuch areas.",
    heading: "Women's Clothing in Neemuch",
    intro: "Discover women’s fashion from local Neemuch stores, including tops, jeans, kurtas, co-ords and occasion wear. Compare local choices online before you order.",
    category: 'Clothing & Fashion',
    department: 'women',
  },
  {
    slug: 'kids-wear',
    label: 'Kids Wear',
    title: 'Kids Wear in Neemuch | Boys & Girls Clothing | Vibe4You',
    description: 'Shop kids wear in Neemuch from local sellers. Browse clothing for boys, girls and younger children with local ordering and Same Day Delivery in supported areas.',
    heading: 'Kids Wear in Neemuch',
    intro: 'Find kids clothing from Neemuch stores in one catalogue. Browse local options for boys and girls and order from nearby sellers through Vibe4You.',
    category: 'Clothing & Fashion',
    department: 'kids',
  },
  {
    slug: 'watches',
    label: 'Watches in Neemuch',
    title: 'Buy Watches in Neemuch | Men & Women Watches | Vibe4You',
    description: 'Shop watches in Neemuch from local stores on Vibe4You. Browse analog, fashion and everyday watches with local availability and Same Day Delivery in supported areas.',
    heading: 'Buy Watches in Neemuch',
    intro: 'Looking for watches in Neemuch? Browse watches stocked by local stores, compare styles and prices, and order from nearby sellers through Vibe4You.',
    category: 'Accessories',
    subcategories: ['Watches'],
    nameTerms: ['watch'],
  },
  {
    slug: 'jewellery',
    label: 'Jewellery in Neemuch',
    title: 'Jewellery in Neemuch | Earrings, Bangles & Necklaces | Vibe4You',
    description: 'Shop fashion jewellery in Neemuch from local sellers. Browse earrings, bangles, necklaces, bracelets and more on Vibe4You.',
    heading: 'Fashion Jewellery in Neemuch',
    intro: 'Explore fashion jewellery sold by local Neemuch shops, including earrings, bangles, necklaces and bracelets. Browse styles online and buy locally through Vibe4You.',
    category: 'Accessories',
    subcategories: ['Fashion Jewellery', 'Earrings', 'Bangles', 'Necklaces', 'Bracelets'],
    nameTerms: ['earring', 'bangle', 'necklace', 'bracelet', 'jewellery', 'jewelry', 'jhumki'],
  },
  {
    slug: 'beauty',
    label: 'Beauty & Personal Care',
    title: 'Beauty & Personal Care in Neemuch | Shop Local Online | Vibe4You',
    description: 'Buy beauty and personal care products in Neemuch from local stores. Browse hair care, skin care, perfumes, baby care and more on Vibe4You.',
    heading: 'Beauty & Personal Care in Neemuch',
    intro: 'Shop beauty and personal care products available from local Neemuch sellers, including hair care, skin care, perfumes, baby care and daily essentials.',
    category: 'Beauty & Personal Care',
  },
  {
    slug: 'gifts',
    label: 'Gifts in Neemuch',
    title: 'Buy Gifts in Neemuch | Local Gift Shopping & Delivery | Vibe4You',
    description: 'Find gifts in Neemuch from local sellers on Vibe4You. Browse gift options online and order locally with Same Day Delivery in the supported Neemuch area.',
    heading: 'Buy Gifts in Neemuch',
    intro: 'Need a gift in Neemuch? Browse gift options from local sellers, compare available products and order without searching store by store.',
    category: 'Gifts',
  },
  {
    slug: 'same-day-delivery',
    label: 'Same Day Delivery',
    title: 'Same Day Delivery in Neemuch | Shop Local Products Online | Vibe4You',
    description: 'Shop products from local Neemuch stores with Same Day Delivery across the supported service area. Browse fashion, footwear, beauty, accessories, gifts and more.',
    heading: 'Same Day Shopping & Delivery in Neemuch',
    intro: 'Vibe4You brings products from local Neemuch stores into one online catalogue. Browse what is available nearby and get eligible local orders delivered the same day in the supported service area.',
    allProducts: true,
  },
  {"slug": "shops", "label": "Local Shops in Neemuch", "title": "Local Shops in Neemuch | Shop Online from Neemuch Stores | Vibe4You", "description": "Find local shops in Neemuch on Vibe4You. Browse every participating Neemuch store, see what each sells and order online with Same Day Delivery in supported areas.", "heading": "Local Shops in Neemuch", "intro": "Looking for shops in Neemuch? Vibe4You brings local Neemuch stores online in one place. Open any shop to see its products, compare prices and order with Same Day Delivery in supported areas.", "catalogueUrl": "/stores", "directory": "stores"},
  {"slug": "casio-watches", "label": "Casio Watches in Neemuch", "title": "Casio Watches in Neemuch | Buy Casio Watch Online | Vibe4You", "description": "Browse Casio watches on Vibe4You with prices, photos and availability. Same Day Delivery in supported Neemuch areas; outside Neemuch, request a prepaid delivery quote.", "heading": "Casio Watches in Neemuch", "intro": "Looking for a Casio watch in Neemuch? Browse Casio digital, analog and everyday models, compare prices and photos, and order with Same Day Delivery in supported Neemuch areas. Outside Neemuch, request a prepaid delivery quote before ordering.", "nameTerms": ["casio"], "catalogueUrl": "/products?category=Accessories&subcategory=Watches"},
  {"slug": "lavie-bags", "label": "Lavie Bags in Neemuch", "title": "Lavie Bags in Neemuch | Handbags, Slings & Wallets | Vibe4You", "description": "Shop Lavie handbags, sling bags and wallets on Vibe4You. See current prices, colours and photos. Same Day Delivery in supported Neemuch areas; prepaid delivery quote outside Neemuch.", "heading": "Lavie Bags in Neemuch", "intro": "Looking for a Lavie bag in Neemuch? Browse Lavie handbags, sling bags and wallets, compare colours and prices, and order with Same Day Delivery in supported Neemuch areas. Outside Neemuch, request a prepaid delivery quote before ordering.", "nameTerms": ["lavie"], "catalogueUrl": "/products?category=Accessories&subcategory=Handbags"},
  {"slug": "handbags", "label": "Handbags & Ladies Bags in Neemuch", "title": "Handbags & Ladies Bags in Neemuch | Buy Bags Online | Vibe4You", "description": "Shop handbags, sling bags and ladies bags in Neemuch from local sellers on Vibe4You. Compare styles and prices with Same Day Delivery in supported areas.", "heading": "Handbags & Ladies Bags in Neemuch", "intro": "Find handbags, sling bags and everyday ladies bags from Neemuch sellers. Browse current styles and prices in one place and order locally through Vibe4You.", "category": "Accessories", "subcategories": ["Handbags"], "nameTerms": ["handbag", "sling bag"], "catalogueUrl": "/products?category=Accessories&subcategory=Handbags"},
  {"slug": "electronics", "label": "Electronics in Neemuch", "title": "Electronics in Neemuch | Mobiles, Covers & Accessories | Vibe4You", "description": "Shop electronics in Neemuch from local stores on Vibe4You. Browse mobile phones, covers, chargers, audio and accessories with Same Day Delivery in supported areas.", "heading": "Electronics in Neemuch", "intro": "Browse electronics from local Neemuch stores, including mobile phones, phone covers, chargers, audio and everyday accessories. Compare options online and order locally through Vibe4You.", "category": "Electronics", "catalogueUrl": "/products?category=Electronics"},
  {"slug": "mobile-phones", "label": "Mobile Phones in Neemuch", "title": "Mobile Phones in Neemuch | Buy Smartphones Online | Vibe4You", "description": "Buy mobile phones in Neemuch from local stores on Vibe4You. Compare smartphones and prices online with Same Day Delivery in supported areas.", "heading": "Mobile Phones in Neemuch", "intro": "Looking for a mobile phone in Neemuch? Compare smartphones listed by local Neemuch stores, check current prices and order through Vibe4You.", "category": "Electronics", "subcategories": ["Mobile Phones"], "catalogueUrl": "/products?category=Electronics&subcategory=Mobile%20Phones"},
  {"slug": "mobile-covers", "label": "Mobile Covers in Neemuch", "title": "Mobile Covers in Neemuch | Phone Cases Online | Vibe4You", "description": "Shop mobile covers and phone cases in Neemuch from local sellers on Vibe4You. Browse designs and prices with Same Day Delivery in supported areas.", "heading": "Mobile Covers in Neemuch", "intro": "Find phone covers and cases from Neemuch sellers. Browse current designs, compare prices and order locally through Vibe4You.", "category": "Electronics", "subcategories": ["Mobile Covers"], "catalogueUrl": "/products?category=Electronics&subcategory=Mobile%20Covers"},
  {"slug": "mobile-accessories", "label": "Mobile Accessories in Neemuch", "title": "Mobile Accessories in Neemuch | Chargers, Cables & More | Vibe4You", "description": "Buy mobile accessories in Neemuch from local stores on Vibe4You. Browse chargers, cables, earphones and more with Same Day Delivery in supported areas.", "heading": "Mobile Accessories in Neemuch", "intro": "Shop mobile accessories sold by Neemuch stores, including chargers, cables and everyday add-ons. Compare options and order locally through Vibe4You.", "category": "Electronics", "subcategories": ["Mobile Accessories"], "catalogueUrl": "/products?category=Electronics&subcategory=Mobile%20Accessories"},
  {"slug": "groceries", "label": "Groceries in Neemuch", "title": "Groceries in Neemuch | Buy Grocery Items Online | Vibe4You", "description": "Shop groceries in Neemuch from local stores on Vibe4You. Browse tea, coffee, rice, spices, oils and daily essentials with Same Day Delivery in supported areas.", "heading": "Groceries in Neemuch", "intro": "Order groceries from local Neemuch stores, including tea and coffee, rice and grains, spices, oils and daily essentials. Compare items online and get Same Day Delivery in supported areas.", "category": "Groceries", "catalogueUrl": "/products?category=Groceries"},
  {"slug": "home-and-living", "label": "Home & Kitchen Products in Neemuch", "title": "Home & Kitchen Products in Neemuch | Shop Online | Vibe4You", "description": "Shop home and kitchen products in Neemuch from local stores on Vibe4You. Browse kitchen appliances and home essentials with Same Day Delivery in supported areas.", "heading": "Home & Kitchen Products in Neemuch", "intro": "Find home and kitchen products from local Neemuch stores, including kitchen appliances and household essentials. Compare options online and order locally through Vibe4You.", "category": "Home & Living", "catalogueUrl": "/products?category=Home%20%26%20Living"},
];

export const neemuchShoppingPageBySlug = (slug?: string): NeemuchShoppingPageConfig | undefined =>
  NEEMUCH_SHOPPING_PAGES.find(page => page.slug === slug);
