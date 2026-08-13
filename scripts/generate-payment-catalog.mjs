import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';

const sourcePath = resolve('src/data/products.ts');
const outputPath = resolve('server/payment-data/catalog.json');
const source = await readFile(sourcePath, 'utf8');
const marker = 'export const PRODUCTS: Product[] =';
const markerIndex = source.indexOf(marker);

if (markerIndex === -1) {
  throw new Error(`Could not find ${marker} in ${sourcePath}`);
}

const arrayStart = source.indexOf('[', markerIndex + marker.length);
const arrayEnd = source.lastIndexOf('];');
if (arrayStart === -1 || arrayEnd === -1 || arrayEnd <= arrayStart) {
  throw new Error('Could not locate the product array');
}

const products = JSON.parse(source.slice(arrayStart, arrayEnd + 1));
const catalog = products.map((product) => ({
  id: product.id,
  name: product.name,
  slug: product.slug,
  active: product.active === true,
  price: product.price,
  variants: product.variants.map((variant) => ({
    id: variant.id,
    sku: variant.sku,
    size: variant.size,
    colourName: variant.colourName,
    stock: variant.stock,
    price: variant.price ?? product.price,
  })),
}));

await mkdir(dirname(outputPath), { recursive: true });
await writeFile(outputPath, `${JSON.stringify(catalog, null, 2)}\n`, 'utf8');
console.log(`Generated secure payment catalog with ${catalog.length} products.`);
