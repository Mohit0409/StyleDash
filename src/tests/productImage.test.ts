import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { prepareProductImage } from '../utils/productImage';

describe('iPhone product image preparation', () => {
  let canvas: {
    width: number;
    height: number;
    getContext: ReturnType<typeof vi.fn>;
    toBlob: ReturnType<typeof vi.fn>;
  };

  const imageFile = (type: string, name: string, size = 2 * 1024 * 1024) =>
    ({ type, name, size } as File);

  beforeEach(() => {
    canvas = {
      width: 0,
      height: 0,
      getContext: vi.fn(() => ({ drawImage: vi.fn() })),
      toBlob: vi.fn(),
    };
    vi.stubGlobal('document', { createElement: vi.fn(() => canvas) });
    vi.stubGlobal('createImageBitmap', vi.fn(async () => ({
      width: 2400, height: 1800, close: vi.fn(),
    })));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('automatically reduces detailed iPhone HEIC photos below 500 KB', async () => {
    canvas.toBlob.mockImplementation((callback: (blob: Blob) => void, type: string) => {
      const size = canvas.width >= 1600 ? 530 * 1024 : 320 * 1024;
      callback(new Blob([new Uint8Array(size)], { type }));
    });
    const result = await prepareProductImage(imageFile('image/heic', 'IMG_0091.HEIC'));
    expect(result.fileName).toBe('IMG_0091.webp');
    expect(result.blob.type).toBe('image/webp');
    expect(result.blob.size).toBeLessThanOrEqual(500 * 1024);
    expect(result.width).toBe(1200);
  });

  it('accepts HEIF photos reported as octet-stream by mobile browsers', async () => {
    canvas.toBlob.mockImplementation((callback: (blob: Blob) => void, type: string) => {
      callback(new Blob([new Uint8Array(20 * 1024)], { type }));
    });
    const result = await prepareProductImage(imageFile('application/octet-stream', 'iphone.HEIF'));
    expect(result.fileName).toBe('iphone.webp');
  });

  it('falls back to a valid JPEG when the browser cannot encode WebP', async () => {
    canvas.toBlob.mockImplementation((callback: (blob: Blob) => void, type: string) => {
      callback(new Blob([new Uint8Array(20 * 1024)], { type: type === 'image/webp' ? 'image/png' : 'image/jpeg' }));
    });
    const result = await prepareProductImage(imageFile('image/jpeg', 'front.jpg'));
    expect(result.blob.type).toBe('image/jpeg');
    expect(result.fileName).toBe('front.jpg');
  });

  it('keeps transparent PNG store logos when WebP encoding is unavailable', async () => {
    canvas.toBlob.mockImplementation((callback: (blob: Blob) => void) => {
      callback(new Blob([new Uint8Array(20 * 1024)], { type: 'image/png' }));
    });
    const result = await prepareProductImage(imageFile('image/png', 'shop-logo.png'));
    expect(result.blob.type).toBe('image/png');
    expect(result.fileName).toBe('shop-logo.png');
  });

  it('rejects unsupported formats and source files above 20 MB', async () => {
    await expect(prepareProductImage(imageFile('text/plain', 'bad.txt'))).rejects.toThrow('Choose a JPEG');
    await expect(prepareProductImage(imageFile('image/heic', 'large.heic', 21 * 1024 * 1024))).rejects.toThrow('20 MB');
  });
});
