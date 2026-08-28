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
  const ink = inverse
    ? 'text-[#f7f3ee]'
    : 'text-neutral-950 dark:text-[#f7f3ee]';
  const taglineInk = inverse
    ? 'text-neutral-400'
    : 'text-neutral-600 dark:text-neutral-400';

  return (
    <span className={`inline-flex max-w-full flex-col items-center leading-none ${ink} ${className}`}>
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 540 112"
        role="img"
        aria-label="Vibe4You"
        className="block h-auto w-full overflow-visible"
      >
        <g
          fill="none"
          stroke="currentColor"
          strokeWidth="9.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M9 41 35 83 61 41" />
          <path d="M80 43V83" />
          <path d="M103 20V82M103 52C112 42 125 39 138 42 151 45 158 54 158 63 158 76 147 84 132 84 116 84 105 77 103 67" />
          <path d="M216 65H166C168 50 178 42 192 42 207 42 217 52 217 64 217 77 205 84 191 84 178 84 169 77 166 67" />
        </g>
        <circle cx="80" cy="24" r="5.5" fill="#c88f70" />

        <g
          fill="none"
          stroke="#aaa8a5"
          strokeWidth="13.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity="0.92"
        >
          <path d="M329 23 289 79 350 70M326 38 314 107" />
        </g>
        <g
          fill="none"
          stroke="currentColor"
          strokeWidth="14.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M291 8 229 79 307 68M286 25 270 108" />
        </g>

        <g
          fill="none"
          stroke="currentColor"
          strokeWidth="9.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M354 42 379 82 367 106M405 42 379 82" />
          <ellipse cx="438" cy="63" rx="27" ry="21" />
          <path d="M477 42V64C477 77 486 84 500 84 515 84 524 76 524 63V42" />
        </g>
      </svg>

      {showTagline && (
        <span className={`mt-1 whitespace-nowrap text-center text-[clamp(0.45rem,1.7vw,0.625rem)] font-medium tracking-normal ${taglineInk}`}>
          {CONFIG.TAGLINE}
        </span>
      )}
    </span>
  );
};
