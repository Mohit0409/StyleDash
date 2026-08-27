import React, { useId } from 'react';
import { CONFIG } from '../config';

interface BrandWordmarkProps {
  showTagline?: boolean;
  inverse?: boolean;
  className?: string;
}

const firstFourPath = [
  'M263 6',
  'L213 70',
  'V84',
  'H264',
  'V105',
  'H283',
  'V84',
  'H299',
  'V67',
  'H283',
  'V6',
  'Z',
  'M264 34',
  'V67',
  'H239',
  'Z',
].join(' ');

const secondFourPath = [
  'M320 16',
  'L263 75',
  'V89',
  'H316',
  'V110',
  'H336',
  'V89',
  'H352',
  'V72',
  'H336',
  'V16',
  'Z',
  'M316 45',
  'V72',
  'H290',
  'Z',
].join(' ');

export const BrandWordmark: React.FC<BrandWordmarkProps> = ({
  showTagline = false,
  inverse = false,
  className = '',
}) => {
  const gradientId = `vibe4you-copper-${useId().replace(/:/g, '')}`;
  const shadowId = `vibe4you-shadow-${useId().replace(/:/g, '')}`;
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
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0.9" y2="1">
            <stop offset="0" stopColor="#efc5ad" />
            <stop offset="0.48" stopColor="#c89c84" />
            <stop offset="1" stopColor="#a86750" />
          </linearGradient>
          <filter id={shadowId} x="-12%" y="-10%" width="130%" height="135%">
            <feDropShadow dx="0" dy="2" stdDeviation="1.35" floodColor="#3f241c" floodOpacity="0.28" />
          </filter>
        </defs>

        <g
          fill="none"
          stroke="currentColor"
          strokeWidth="9.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M9 41 35 83 61 41" />
          <path d="M80 43V83" />
          <circle cx="80" cy="24" r="5.5" fill="currentColor" stroke="none" />
          <path d="M103 20V82M103 52C112 42 125 39 138 42 151 45 158 54 158 63 158 76 147 84 132 84 116 84 105 77 103 67" />
          <path d="M216 65H166C168 50 178 42 192 42 207 42 217 52 217 64 217 77 205 84 191 84 178 84 169 77 166 67" />
        </g>

        <g
          fill={`url(#${gradientId})`}
          fillRule="evenodd"
          stroke="#754939"
          strokeWidth="2.2"
          strokeLinejoin="miter"
          paintOrder="stroke fill"
          filter={`url(#${shadowId})`}
        >
          <path d={firstFourPath} />
          <path d={secondFourPath} />
        </g>
        <path d="M260 11 218 73H265" fill="none" stroke="#f4d4c2" strokeWidth="2" strokeLinecap="square" opacity="0.72" />
        <path d="M317 21 269 78H317" fill="none" stroke="#f4d4c2" strokeWidth="2" strokeLinecap="square" opacity="0.65" />

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
