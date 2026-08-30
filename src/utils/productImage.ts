const MAX_SOURCE_BYTES = 12 * 1024 * 1024;
const TARGET_BYTES = 350 * 1024;
const MAX_OUTPUT_BYTES = 500 * 1024;
const MAX_DIMENSION = 1600;
const FALLBACK_DIMENSION = 1200;
const ALLOWED_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp']);

export interface PreparedProductImage {
  blob: Blob;
  fileName: string;
  width: number;
  height: number;
}

const canvasBlob = (canvas: HTMLCanvasElement, type: string, quality: number) =>
  new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('Image compression failed.')), type, quality);
  });

const fit = (width: number, height: number, maximum: number) => {
  if (Math.max(width, height) <= maximum) return { width, height };
  const scale = maximum / Math.max(width, height);
  return { width: Math.max(1, Math.round(width * scale)), height: Math.max(1, Math.round(height * scale)) };
};const render = (source: CanvasImageSource, sourceWidth: number, sourceHeight: number, maximum: number) => {
  const dimensions = fit(sourceWidth, sourceHeight, maximum);
  const canvas = document.createElement('canvas');
  canvas.width = dimensions.width;
  canvas.height = dimensions.height;
  const context = canvas.getContext('2d', { alpha: true });
  if (!context) throw new Error('Image processing is unavailable in this browser.');
  context.drawImage(source, 0, 0, dimensions.width, dimensions.height);
  return { canvas, ...dimensions };
};

const loadBitmap = async (file: File): Promise<ImageBitmap> => {
  if (typeof createImageBitmap !== 'function') {
    throw new Error('Image processing is unavailable in this browser.');
  }
  return createImageBitmap(file, { imageOrientation: 'from-image' });
};

export async function prepareProductImage(file: File): Promise<PreparedProductImage> {
  if (!ALLOWED_TYPES.has(file.type)) throw new Error('Choose a JPEG, PNG or WebP image.');
  if (file.size <= 0 || file.size > MAX_SOURCE_BYTES) throw new Error('Choose an image smaller than 12 MB.');

  const bitmap = await loadBitmap(file);
  try {
    let rendered = render(bitmap, bitmap.width, bitmap.height, MAX_DIMENSION);
    let blob = await canvasBlob(rendered.canvas, 'image/webp', 0.82);
    for (const quality of [0.72, 0.62, 0.52]) {
      if (blob.size <= TARGET_BYTES) break;
      blob = await canvasBlob(rendered.canvas, 'image/webp', quality);
    }    if (blob.size > MAX_OUTPUT_BYTES && Math.max(rendered.width, rendered.height) > FALLBACK_DIMENSION) {
      rendered = render(bitmap, bitmap.width, bitmap.height, FALLBACK_DIMENSION);
      blob = await canvasBlob(rendered.canvas, 'image/webp', 0.62);
    }
    if (blob.size > MAX_OUTPUT_BYTES) throw new Error('This image is still too large after compression. Choose a simpler or smaller image.');

    return {
      blob,
      fileName: `${file.name.replace(/\.[^.]+$/, '').slice(0, 80) || 'product'}.webp`,
      width: rendered.width,
      height: rendered.height,
    };
  } finally {
    bitmap.close();
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