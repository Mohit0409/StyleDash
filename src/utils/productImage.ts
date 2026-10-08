const MAX_SOURCE_BYTES = 20 * 1024 * 1024;
const TARGET_BYTES = 350 * 1024;
const MAX_OUTPUT_BYTES = 500 * 1024;
const MAX_DIMENSION = 1600;
const FALLBACK_DIMENSION = 1200;
const ALLOWED_TYPES = new Set([
  'image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif',
]);
const EXTENSION_TYPES: Record<string, string> = {
  jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', webp: 'image/webp',
  heic: 'image/heic', heif: 'image/heif',
};

export const PRODUCT_IMAGE_ACCEPT =
  'image/jpeg,image/png,image/webp,image/heic,image/heif,.heic,.heif';

export interface PreparedProductImage {
  blob: Blob;
  fileName: string;
  width: number;
  height: number;
}

interface LoadedImage {
  source: CanvasImageSource;
  width: number;
  height: number;
  release: () => void;
}

const resolvedType = (file: File) => {
  const declared = file.type.trim().toLowerCase();
  if (declared && declared !== 'application/octet-stream') return declared;
  const extension = file.name.split('.').pop()?.toLowerCase() || '';
  return EXTENSION_TYPES[extension] || '';
};

const canvasBlob = (canvas: HTMLCanvasElement, type: string, quality: number) =>
  new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      blob => blob ? resolve(blob) : reject(new Error('Image compression failed.')),
      type,
      quality,
    );
  });

const fit = (width: number, height: number, maximum: number) => {
  if (Math.max(width, height) <= maximum) return { width, height };
  const scale = maximum / Math.max(width, height);
  return {
    width: Math.max(1, Math.round(width * scale)),
    height: Math.max(1, Math.round(height * scale)),
  };
};

const render = (
  source: CanvasImageSource,
  sourceWidth: number,
  sourceHeight: number,
  maximum: number,
) => {
  const dimensions = fit(sourceWidth, sourceHeight, maximum);
  const canvas = document.createElement('canvas');
  canvas.width = dimensions.width;
  canvas.height = dimensions.height;
  const context = canvas.getContext('2d', { alpha: true });
  if (!context) throw new Error('Image processing is unavailable in this browser.');

  context.drawImage(source, 0, 0, dimensions.width, dimensions.height);
  return { canvas, ...dimensions };
};

const loadWithImageElement = (file: File) => new Promise<LoadedImage>((resolve, reject) => {
  const image = new Image();
  const reader = new FileReader();
  const failed = () => reject(new Error(
    'This image could not be read by your browser. On iPhone, choose it from Photos or export it as JPEG.',
  ));

  image.onload = () => resolve({
    source: image,
    width: image.naturalWidth,
    height: image.naturalHeight,
    release: () => { image.src = ''; },
  });
  image.onerror = failed;
  reader.onerror = failed;
  reader.onload = () => {
    if (typeof reader.result !== 'string') return failed();
    image.src = reader.result;
  };
  reader.readAsDataURL(file);
});

const loadImage = async (file: File): Promise<LoadedImage> => {
  if (typeof createImageBitmap === 'function') {
    try {
      const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' });
      return {
        source: bitmap,
        width: bitmap.width,
        height: bitmap.height,
        release: () => bitmap.close(),
      };
    } catch {
      // Some iPhone/Safari versions expose createImageBitmap but fail on
      // particular photo sources. Fall back to the browser image decoder.
    }
  }
  return loadWithImageElement(file);
};

export async function prepareProductImage(file: File): Promise<PreparedProductImage> {
  const contentType = resolvedType(file);
  if (!ALLOWED_TYPES.has(contentType)) {
    throw new Error('Choose a JPEG, PNG, WebP, HEIC or HEIF image.');
  }

  if (file.size <= 0 || file.size > MAX_SOURCE_BYTES) {
    throw new Error('Choose an image smaller than 20 MB.');
  }

  const loaded = await loadImage(file);
  try {
    // Large phone photos can exceed 500 KB even after the first resize.
    for (const dimension of [MAX_DIMENSION, FALLBACK_DIMENSION, 960, 768, 640]) {
      const rendered = render(loaded.source, loaded.width, loaded.height, dimension);
      for (const quality of [0.82, 0.68, 0.52, 0.38]) {
        let blob = await canvasBlob(rendered.canvas, 'image/webp', quality);
        if (blob.type !== 'image/webp' && !(contentType === 'image/png' && blob.size <= MAX_OUTPUT_BYTES)) {
          // Older Safari may return PNG for WebP; try JPEG as a fallback.
          const jpeg = await canvasBlob(rendered.canvas, 'image/jpeg', quality);
          if (jpeg.type === 'image/jpeg') blob = jpeg;
        }
        if (blob.size > MAX_OUTPUT_BYTES) continue;
        if (blob.size > TARGET_BYTES && quality > 0.52) continue;
        const extension = blob.type === 'image/jpeg' ? 'jpg' : blob.type === 'image/png' ? 'png' : 'webp';
        return {
          blob,
          fileName: `${file.name.replace(/\.[^.]+$/, '').slice(0, 80) || 'product'}.${extension}`,
          width: rendered.width,
          height: rendered.height,
        };
      }
    }
    throw new Error('This photo could not be compressed below 500 KB. Please choose a smaller photo.');
  } finally {
    loaded.release();
  }
}

export async function blobToBase64(blob: Blob): Promise<string> {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let binary = '';
  const chunk = 0x8000;
  for (let index = 0; index < bytes.length; index += chunk) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunk));
  }
  return btoa(binary);
}
