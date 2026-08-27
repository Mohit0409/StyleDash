import React from 'react';
import { CONFIG } from '../config';

interface BrandWordmarkProps {
  showTagline?: boolean;
  inverse?: boolean;
  className?: string;
}

export const BrandWordmark: React.FC<BrandWordmarkProps> = ({
  showTagline = false,
  inverse = false,
  className = '',
}) => {
  const ink = inverse ? 'text-white' : 'text-neutral-950 dark:text-white';

  return <span className={`inline-flex flex-col ${className}`}>
    <span aria-label="vibe4you" className={`inline-flex items-center font-black tracking-[-0.07em] leading-none ${ink}`}>
      <span>vibe</span>
      <span className="relative mx-[-0.02em] inline-block w-[1.38em] text-[#b79a8a]" aria-hidden="true">
        <span className="absolute left-0 top-0">4</span>
        <span className="absolute left-[0.42em] top-[0.05em]">4</span>
        <span className="invisible">44</span>
      </span>
      <span>you</span>
    </span>
    {showTagline && <span className="mt-1 text-[9px] font-semibold tracking-[0.08em] text-neutral-500 dark:text-neutral-400 sm:text-[10px]">
      {CONFIG.TAGLINE}
    </span>}
  </span>;
};
