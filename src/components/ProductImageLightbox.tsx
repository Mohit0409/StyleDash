import React, { useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Minus, Plus, RotateCcw, X } from 'lucide-react';

interface ProductImageLightboxProps {
  imageUrls: string[];
  selectedImage: string;
  productName: string;
  isOpen: boolean;
  onSelectImage: (imageUrl: string) => void;
  onClose: () => void;
}

type Point = { x: number; y: number };

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);

/**
 * A deliberately dependency-free product viewer. It retains the original image URL,
 * contains it by default, and only clips while a customer intentionally zooms in.
 */
export const ProductImageLightbox: React.FC<ProductImageLightboxProps> = ({
  imageUrls,
  selectedImage,
  productName,
  isOpen,
  onSelectImage,
  onClose,
}) => {
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const pointersRef = useRef(new Map<number, Point>());
  const pinchStartRef = useRef<{ distance: number; zoom: number } | null>(null);
  const swipeStartRef = useRef<Point | null>(null);
  const zoomRef = useRef(1);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState<Point>({ x: 0, y: 0 });

  const selectedIndex = Math.max(0, imageUrls.indexOf(selectedImage));
  const hasMultipleImages = imageUrls.length > 1;

  const resetZoom = () => {
    zoomRef.current = 1;
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const setZoomLevel = (nextZoom: number) => {
    const boundedZoom = clamp(nextZoom, 1, 3);
    zoomRef.current = boundedZoom;
    setZoom(boundedZoom);
    if (boundedZoom === 1) setPan({ x: 0, y: 0 });
  };

  const selectIndex = (index: number) => {
    if (!imageUrls.length) return;
    onSelectImage(imageUrls[(index + imageUrls.length) % imageUrls.length]);
    resetZoom();
  };

  const selectPrevious = () => selectIndex(selectedIndex - 1);
  const selectNext = () => selectIndex(selectedIndex + 1);

  useEffect(() => {
    if (!isOpen) return;

    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.requestAnimationFrame(() => closeButtonRef.current?.focus());

    return () => {
      document.body.style.overflow = originalOverflow;
      previousFocusRef.current?.focus();
    };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key === 'ArrowLeft' && hasMultipleImages) {
        event.preventDefault();
        selectPrevious();
        return;
      }
      if (event.key === 'ArrowRight' && hasMultipleImages) {
        event.preventDefault();
        selectNext();
        return;
      }
      if (event.key !== 'Tab') return;

      const focusable = Array.from(dialogRef.current?.querySelectorAll<HTMLButtonElement>('button:not([disabled])') || []);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [hasMultipleImages, isOpen, onClose, selectedIndex]);

  useEffect(() => {
    resetZoom();
  }, [selectedImage]);

  const onPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    pointersRef.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (pointersRef.current.size === 1) swipeStartRef.current = { x: event.clientX, y: event.clientY };
    if (pointersRef.current.size === 2) {
      const [first, second] = Array.from(pointersRef.current.values());
      pinchStartRef.current = { distance: Math.hypot(first.x - second.x, first.y - second.y), zoom: zoomRef.current };
    }
  };

  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const previousPoint = pointersRef.current.get(event.pointerId);
    if (!previousPoint) return;
    const nextPoint = { x: event.clientX, y: event.clientY };
    pointersRef.current.set(event.pointerId, nextPoint);

    if (pointersRef.current.size >= 2 && pinchStartRef.current) {
      const [first, second] = Array.from(pointersRef.current.values());
      const distance = Math.hypot(first.x - second.x, first.y - second.y);
      if (pinchStartRef.current.distance > 0) {
        setZoomLevel(pinchStartRef.current.zoom * (distance / pinchStartRef.current.distance));
      }
      return;
    }

    if (zoomRef.current > 1) {
      const maxPan = (zoomRef.current - 1) * 45;
      setPan(current => ({
        x: clamp(current.x + nextPoint.x - previousPoint.x, -maxPan, maxPan),
        y: clamp(current.y + nextPoint.y - previousPoint.y, -maxPan, maxPan),
      }));
    }
  };

  const onPointerEnd = (event: React.PointerEvent<HTMLDivElement>) => {
    const swipeStart = swipeStartRef.current;
    const isSinglePointerSwipe = pointersRef.current.size === 1 && zoomRef.current === 1 && swipeStart;
    pointersRef.current.delete(event.pointerId);
    if (pointersRef.current.size < 2) pinchStartRef.current = null;
    if (pointersRef.current.size === 0) swipeStartRef.current = null;

    if (isSinglePointerSwipe && Math.abs(event.clientX - swipeStart.x) > 48) {
      if (event.clientX < swipeStart.x) selectNext();
      else selectPrevious();
    }
  };

  if (!isOpen || !selectedImage) return null;

  return (
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-label={`${productName} image viewer`}
      className="fixed inset-0 z-[100] flex items-center justify-center bg-neutral-950/95 p-3 text-white backdrop-blur-sm sm:p-6"
      onPointerDown={event => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="relative flex h-full w-full max-w-6xl flex-col">
        <div className="flex items-center justify-between gap-3 pb-3 text-xs font-bold text-neutral-200">
          <p aria-live="polite">Image {selectedIndex + 1} of {imageUrls.length}</p>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            aria-label="Close image viewer"
            className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-full bg-white/10 text-white transition hover:bg-white/20 focus:outline-none focus:ring-2 focus:ring-lime-400"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div
          data-product-image-lightbox-canvas
          className={`relative flex min-h-0 flex-1 items-center justify-center overflow-hidden rounded-2xl bg-neutral-900/70 ${zoom > 1 ? 'cursor-grab active:cursor-grabbing' : 'cursor-zoom-in'}`}
          style={{ touchAction: 'none' }}
          onPointerDown={event => {
            if (event.target === event.currentTarget && zoom === 1) {
              onClose();
              return;
            }
            onPointerDown(event);
          }}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerEnd}
          onPointerCancel={onPointerEnd}
        >
          <img
            src={selectedImage}
            alt={`${productName}, image ${selectedIndex + 1}`}
            draggable={false}
            className="max-h-full max-w-full select-none object-contain"
            style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`, transition: pointersRef.current.size ? 'none' : 'transform 150ms ease-out' }}
          />

          {hasMultipleImages && <>
            <button type="button" onClick={selectPrevious} aria-label="Previous image" className="absolute left-3 top-1/2 inline-flex min-h-11 min-w-11 -translate-y-1/2 items-center justify-center rounded-full bg-black/55 text-white transition hover:bg-black/80 focus:outline-none focus:ring-2 focus:ring-lime-400 sm:left-5">
              <ChevronLeft className="h-6 w-6" />
            </button>
            <button type="button" onClick={selectNext} aria-label="Next image" className="absolute right-3 top-1/2 inline-flex min-h-11 min-w-11 -translate-y-1/2 items-center justify-center rounded-full bg-black/55 text-white transition hover:bg-black/80 focus:outline-none focus:ring-2 focus:ring-lime-400 sm:right-5">
              <ChevronRight className="h-6 w-6" />
            </button>
          </>}
        </div>

        <div className="flex items-center justify-center gap-2 pt-3">
          <button type="button" onClick={() => setZoomLevel(zoom - 0.5)} disabled={zoom <= 1} aria-label="Zoom out" className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-full bg-white/10 text-white transition hover:bg-white/20 disabled:cursor-not-allowed disabled:opacity-40 focus:outline-none focus:ring-2 focus:ring-lime-400"><Minus className="h-4 w-4" /></button>
          <button type="button" onClick={resetZoom} disabled={zoom === 1 && pan.x === 0 && pan.y === 0} aria-label="Reset zoom" className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-full bg-white/10 text-white transition hover:bg-white/20 disabled:cursor-not-allowed disabled:opacity-40 focus:outline-none focus:ring-2 focus:ring-lime-400"><RotateCcw className="h-4 w-4" /></button>
          <button type="button" onClick={() => setZoomLevel(zoom + 0.5)} disabled={zoom >= 3} aria-label="Zoom in" className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-full bg-white/10 text-white transition hover:bg-white/20 disabled:cursor-not-allowed disabled:opacity-40 focus:outline-none focus:ring-2 focus:ring-lime-400"><Plus className="h-4 w-4" /></button>
        </div>
        <p className="pt-2 text-center text-[11px] text-neutral-400">Use pinch or the zoom controls to inspect details. Swipe or use the arrows to browse images.</p>
      </div>
    </div>
  );
};
