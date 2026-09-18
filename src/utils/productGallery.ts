export const productGalleryImages = (
  productImages: string[],
  variantImages?: string[],
): string[] => {
  const product = productImages.filter(Boolean);
  const variant = (variantImages || []).filter(Boolean);

  if (variant.length === 0) return product;

  // Seller-created variants often inherit only the product's primary image.
  // In that case, keep the colour-specific primary while also exposing the
  // product-level secondary catalogue images. If a variant has a genuinely
  // different image or its own multi-image gallery, keep that gallery isolated
  // so images from another colour are never mixed in.
  if (
    variant.length === 1
    && product.length > 1
    && variant[0] === product[0]
  ) {
    return product;
  }

  return variant;
};
