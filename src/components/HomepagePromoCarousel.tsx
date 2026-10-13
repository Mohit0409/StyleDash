import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, ChevronLeft, ChevronRight, Pause, Play } from 'lucide-react';
import { HOME_PROMO_SLIDES } from '../data/homePromoSlides';
import './HomepagePromoCarousel.css';

const AUTO_ADVANCE_MS = 4500;

export const HomepagePromoCarousel: React.FC = () => {
  const railRef = useRef<HTMLDivElement>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [isInteracting, setIsInteracting] = useState(false);
  const [userPaused, setUserPaused] = useState(false);
  const [pageVisible, setPageVisible] = useState(true);
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
    const updatePreference = () => setReducedMotion(preference.matches);
    const updateVisibility = () => setPageVisible(!document.hidden);
    updatePreference();
    updateVisibility();
    preference.addEventListener('change', updatePreference);
    document.addEventListener('visibilitychange', updateVisibility);
    return () => {
      preference.removeEventListener('change', updatePreference);
      document.removeEventListener('visibilitychange', updateVisibility);
    };
  }, []);

  const showSlide = useCallback((index: number) => {
    const rail = railRef.current;
    if (!rail) return;
    const slides = Array.from(rail.querySelectorAll<HTMLElement>('[data-promo-slide]'));
    const target = slides[index];
    if (!target || !slides[0]) return;

    rail.scrollTo({
      left: target.offsetLeft - slides[0].offsetLeft,
      behavior: reducedMotion ? 'auto' : 'smooth',
    });
  }, [reducedMotion]);

  const updateActiveFromScroll = () => {
    const rail = railRef.current;
    if (!rail) return;
    const slides = Array.from(rail.querySelectorAll<HTMLElement>('[data-promo-slide]'));
    if (!slides[0]) return;
    const firstOffset = slides[0].offsetLeft;
    let closest = 0;
    let distance = Infinity;
    for (let index = 0; index < slides.length; index += 1) {
      const nextDistance = Math.abs(slides[index].offsetLeft - firstOffset - rail.scrollLeft);
      if (nextDistance < distance) {
        distance = nextDistance;
        closest = index;
      }
    }
    setActiveIndex(previous => previous === closest ? previous : closest);
  };

  useEffect(() => {
    if (isInteracting || userPaused || !pageVisible || reducedMotion || HOME_PROMO_SLIDES.length < 2) return;
    const timer = window.setInterval(() => {
      showSlide((activeIndex + 1) % HOME_PROMO_SLIDES.length);
    }, AUTO_ADVANCE_MS);
    return () => window.clearInterval(timer);
  }, [activeIndex, isInteracting, userPaused, pageVisible, reducedMotion, showSlide]);

  return (
    <section
      aria-label="Featured Vibe4You collections"
      aria-roledescription="carousel"
      data-testid="homepage-promo-carousel"
      className="vibe-home-promo mx-auto max-w-7xl px-3 sm:px-6 lg:px-8"
    >
      <div className="mb-3 flex items-center justify-between gap-4 px-1">
        <h1 className="text-base font-black text-neutral-900 dark:text-white sm:text-xl">
          Featured for you
        </h1>
        <span className="text-[11px] font-medium text-neutral-500 sm:text-xs">
          Swipe to explore
        </span>
      </div>

      <div
        id="homepage-promo-rail"
        ref={railRef}
        onScroll={updateActiveFromScroll}
        onMouseEnter={() => setIsInteracting(true)}
        onMouseLeave={() => setIsInteracting(false)}
        onTouchStart={() => setIsInteracting(true)}
        onTouchEnd={() => setIsInteracting(false)}
        onTouchCancel={() => setIsInteracting(false)}
        onFocusCapture={() => setIsInteracting(true)}
        onBlurCapture={event => {
          if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
            setIsInteracting(false);
          }
        }}
        className="relative flex snap-x snap-mandatory gap-3 overflow-x-auto overscroll-x-contain scroll-smooth rounded-2xl pb-1 pr-5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden motion-reduce:scroll-auto sm:gap-4"
        data-testid="homepage-promo-rail"
        aria-label="Promotional cards"
      >
        {HOME_PROMO_SLIDES.map((slide, index) => (
          <Link
            key={slide.id}
            to={slide.targetUrl}
            data-promo-slide
            data-testid="homepage-promo-slide"
            className={`group relative block aspect-[1.7/1] min-w-0 flex-[0_0_93%] snap-start overflow-hidden rounded-2xl shadow-md ring-1 ring-black/5 focus-visible:outline focus-visible:outline-4 focus-visible:outline-lime-400 sm:aspect-[2.3/1] sm:flex-[0_0_86%] sm:rounded-3xl lg:aspect-[2.6/1] lg:flex-[0_0_72%] ${slide.backgroundClassName}`}
            aria-label={`Explore ${slide.title}`}
          >
            <img
              src={slide.imageUrl}
              alt=""
              loading={index === 0 ? 'eager' : 'lazy'}
              decoding="async"
              fetchPriority={index === 0 ? 'high' : undefined}
              draggable={false}
              className="absolute inset-0 h-full w-full object-cover object-center transition-transform duration-700 group-hover:scale-105"
            />
            <div className="absolute inset-0 bg-gradient-to-r from-black/90 via-black/65 to-black/10" />
            <div className="relative flex h-full max-w-[82%] flex-col justify-center gap-2 p-5 text-white sm:max-w-[70%] sm:gap-3 sm:p-8 lg:p-10">
              <span className="w-fit rounded-full bg-lime-400 px-2.5 py-1 text-[9px] font-black uppercase tracking-wider text-neutral-950 sm:text-xs">
                {slide.eyebrow}
              </span>
              <h3 className="text-2xl font-black leading-[1.07] tracking-tight drop-shadow-sm sm:text-4xl lg:text-5xl">
                {slide.title}
              </h3>
              <p className="max-w-md text-[11px] font-medium leading-relaxed text-white/90 sm:text-sm lg:text-base">
                {slide.subtitle}
              </p>
              <span className="mt-1 inline-flex w-fit items-center gap-1 rounded-full border border-white/60 bg-white/15 px-3 py-1.5 text-[11px] font-extrabold backdrop-blur-sm transition-colors group-hover:bg-white/30 sm:text-sm">
                {slide.ctaLabel ?? 'Explore now'} <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
              </span>
            </div>
          </Link>
        ))}
      </div>

      <div className="mt-3 flex items-center justify-center gap-4" aria-label="Carousel navigation">
        <button
          type="button"
          onClick={() => showSlide((activeIndex - 1 + HOME_PROMO_SLIDES.length) % HOME_PROMO_SLIDES.length)}
          aria-label="Previous promotion"
          className="hidden min-h-11 min-w-11 items-center justify-center rounded-full border border-neutral-200 text-neutral-700 hover:bg-neutral-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-lime-500 dark:border-neutral-700 dark:text-neutral-200 dark:hover:bg-neutral-800 sm:inline-flex"
        >
          <ChevronLeft className="h-5 w-5" aria-hidden="true" />
        </button>
        <div className="flex items-center gap-2">
          {HOME_PROMO_SLIDES.map((slide, index) => (
            <button
              key={slide.id}
              type="button"
              onClick={() => showSlide(index)}
              aria-label={`Show promotion ${index + 1}: ${slide.title}`}
              aria-current={index === activeIndex ? 'true' : undefined}
              aria-controls="homepage-promo-rail"
              className={`h-2.5 min-w-2.5 rounded-full transition-all focus-visible:outline focus-visible:outline-2 focus-visible:outline-lime-500 ${index === activeIndex ? 'w-7 bg-lime-500' : 'w-2.5 bg-neutral-300 hover:bg-neutral-400 dark:bg-neutral-600'}`}
            />
          ))}
        </div>
        <button
          type="button"
          data-testid="homepage-promo-autoplay-toggle"
          aria-label={
            reducedMotion
              ? 'Automatic promotions disabled by reduced motion setting'
              : userPaused
                ? 'Resume automatic promotions'
                : 'Pause automatic promotions'
          }
          aria-pressed={userPaused}
          disabled={reducedMotion}
          onClick={() => setUserPaused(previous => !previous)}
          className="vibe-home-promo-toggle"
        >
          {userPaused || reducedMotion
            ? <Play className="h-4 w-4" aria-hidden="true" />
            : <Pause className="h-4 w-4" aria-hidden="true" />}
        </button>
        <button
          type="button"
          onClick={() => showSlide((activeIndex + 1) % HOME_PROMO_SLIDES.length)}
          aria-label="Next promotion"
          className="hidden min-h-11 min-w-11 items-center justify-center rounded-full border border-neutral-200 text-neutral-700 hover:bg-neutral-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-lime-500 dark:border-neutral-700 dark:text-neutral-200 dark:hover:bg-neutral-800 sm:inline-flex"
        >
          <ChevronRight className="h-5 w-5" aria-hidden="true" />
        </button>
      </div>
    </section>
  );
};
