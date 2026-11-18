# Original catalogue/seller reconciliation

The eight tracked catalogue-taxonomy and seller paths from the original Windows checkout have been reviewed against the current frontend and backend contracts.

## Decision

`PASS` - port only clearer Selling Price and MRP labels.

The dirty 100-size proposal was rejected because the seller backend authoritatively limits public submissions to 20 active size/colour combinations. The dirty static taxonomy was also rejected: it depends on an untracked file and introduces store categories outside the backend-authorized list. The current customer category page is safer because it derives categories, subcategories, and counts from published products instead of advertising empty static branches.

HEIC/HEIF upload support, sequential preview updates, outside-Neemuch delivery typing, and centralized store categories are already present in stronger current implementations. The current `StoreCategory` union is retained instead of weakening it to `string`.

The seller form now labels the customer price as `Price (Selling Price) (INR)` and the comparison price as `Original price (MRP) (INR)`. Existing browser tests were updated to exercise both labels while retaining seller-review and payload assertions.

The per-file decisions are recorded in [original-catalog-seller-reconciliation.json](../deployment-snapshots/vibe4you-20261116-gst-r2/original-catalog-seller-reconciliation.json).

No catalogue data, seller record, inventory, database, deployment, service, or production state was changed.
