import React, { useEffect, useState } from 'react';
import { Store } from 'lucide-react';

interface StoreImageProps {
  src?: string | null;
  alt: string;
  storeName: string;
  kind: 'cover' | 'logo';
  className?: string;
  loading?: 'eager' | 'lazy';
  decoding?: 'async' | 'auto' | 'sync';
}

/** Remove failed media from the DOM so public pages never show a broken icon. */
export const StoreImage: React.FC<StoreImageProps> = ({
  src,
  alt,
  storeName,
  kind,
  className = '',
  loading,
  decoding,
}) => {
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [src]);

  if (src && !failed) {
    return (
      <img
        src={src}
        alt={alt}
        loading={loading}
        decoding={decoding}
        onError={() => setFailed(true)}
        className={className}
      />
    );
  }

  return (
    <div
      role="img"
      aria-label={`${storeName} ${kind} placeholder`}
      data-store-image-fallback={kind}
      className={`${className} flex items-center justify-center overflow-hidden bg-gradient-to-br from-neutral-100 via-neutral-200 to-neutral-300 text-neutral-500 dark:from-neutral-800 dark:via-neutral-900 dark:to-black dark:text-neutral-400`}
    >
      <div className="flex flex-col items-center gap-1 text-center">
        <Store className={kind === 'cover' ? 'h-10 w-10 sm:h-12 sm:w-12' : 'h-6 w-6'} aria-hidden="true" />
        {kind === 'cover' && (
          <span className="text-[10px] font-black uppercase tracking-[0.2em] sm:text-xs">
            Vibe4You Local Store
          </span>
        )}
      </div>
    </div>
  );
};
