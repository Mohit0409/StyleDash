/** Mobile shortcuts matching the active production storefront without DOM overlays. */
export type MobileCategoryShortcut = {
  label: string;
  href: string;
  position?: string;
  icon?: string;
  backgroundColor?: string;
};

export const MOBILE_CATEGORY_SHORTCUTS: readonly MobileCategoryShortcut[] = [
  { label: "Women", href: "/products?dept=women", position: "0% 0%" },
  { label: "Men", href: "/products?dept=men", position: "50% 0%" },
  { label: "Kids", href: "/products?dept=kids", position: "100% 0%" },
  { label: "Footwear", href: "/products?category=Footwear", position: "0% 100%" },
  { label: "Watches", href: "/products?search=watch", icon: "⌚", backgroundColor: "#eaf1ff" },
  { label: "Groceries", href: "/products?category=Groceries", icon: "🛒", backgroundColor: "#e8f7e5" },
  { label: "Nutrition", href: "/products?category=Health%20%26%20Nutrition", icon: "🍎", backgroundColor: "#e5f6ee" },
  { label: "Beauty", href: "/products?category=Beauty%20%26%20Personal%20Care", position: "50% 100%" },
  { label: "Jewellery", href: "/products?category=Accessories", position: "100% 100%" },
];
