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
    <span aria-label="vibe4you" className={`inline-flex items-end font-black tracking-[-0.075em] leading-none ${ink}`}>
      <span>vibe</span>
      <span
        className="relative mx-[-0.06em] inline-block h-[1.08em] w-[1.44em] shrink-0 text-[#c39a86]"
        aria-hidden="true"
      >
        <span className="absolute bottom-[-0.02em] left-0 text-[1.28em] leading-none">4</span>
        <span className="absolute bottom-[-0.02em] left-[0.39em] text-[1.28em] leading-none">4</span>
      </span>
      <span className="ml-[-0.03em]">you</span>
    </span>
    {showTagline && <span className="mt-1 whitespace-nowrap text-[9px] font-semibold tracking-[0.045em] text-neutral-500 dark:text-neutral-400 sm:text-[10px]">
      {CONFIG.TAGLINE}
    </span>}
  </span>;
};
