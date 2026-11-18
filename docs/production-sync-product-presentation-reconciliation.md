# Original product-presentation/store-detail reconciliation

The five tracked product-presentation and store-detail paths from the original Windows checkout have been reviewed with their untracked dependencies.

## Decision

`PASS` - selectively port the pure presentation helper and the product-page behavior it supports.

Non-fashion products no longer display a fake `Select Size: Default` choice. Multiple options use product-appropriate labels (`Size`, `Pack / Volume`, or `Option`), and size guides appear only for genuinely sized clothing and footwear. Blank, `N/A`, and `Not specified` material/care values are filtered from product information.

On mobile, the main product image is square and the thumbnail rail is hidden; the accessible lightbox remains the full gallery control. Desktop thumbnails remain visible. The product offer metadata now includes its canonical product URL and public seller name.

The reviewed pure helper and its four focused tests were admitted from the previously untracked surface. The ecommerce tracking wrapper and broader assurance component were not admitted. The dirty store structured data was also rejected because it would publish phone and street-address fields without a separate public-contact verification gate.

The current image utility was retained unchanged because it already has stronger HEIC/HEIF decoding, extension fallback, WebP verification, larger input support, and regression coverage.

The per-file decisions are recorded in [original-product-presentation-reconciliation.json](../deployment-snapshots/vibe4you-20261116-gst-r2/original-product-presentation-reconciliation.json).

No product, store, inventory, order, payment, database, deployment, service, or production state was changed.
