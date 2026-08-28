import React, { useEffect } from 'react';

interface SEOProps {
  title?: string;
  description?: string;
  image?: string;
  type?: 'website' | 'product';
  jsonLd?: Record<string, unknown>;
}

const PRODUCTION_ORIGIN = 'https://vibe4you.in';

const ensureMeta = (attribute: 'name' | 'property', key: string, content: string) => {
  let element = document.querySelector<HTMLMetaElement>(`meta[${attribute}="${key}"]`);
  if (!element) {
    element = document.createElement('meta');
    element.setAttribute(attribute, key);
    document.head.appendChild(element);
  }
  element.setAttribute('content', content);
};

const removeMeta = (attribute: 'name' | 'property', key: string) => {
  document.querySelector<HTMLMetaElement>(`meta[${attribute}="${key}"]`)?.remove();
};

export const SEO: React.FC<SEOProps> = ({
  title = 'Vibe4You - Your City. Your Shops. Your Style.',
  description = 'Fashion essentials, trending streetwear, ethnic wear, and footwear delivered from nearby stores in Neemuch within 60 minutes.',
  image,
  type = 'website',
  jsonLd,
}) => {
  useEffect(() => {
    const resolvedTitle = title.includes('Vibe4You') ? title : `${title} | Vibe4You`;
    const canonicalUrl = `${PRODUCTION_ORIGIN}${window.location.pathname}`;
    const imageUrl = image ? new URL(image, PRODUCTION_ORIGIN).href : null;

    document.title = resolvedTitle;
    ensureMeta('name', 'description', description);
    ensureMeta('property', 'og:title', resolvedTitle);
    ensureMeta('property', 'og:description', description);
    ensureMeta('property', 'og:url', canonicalUrl);
    ensureMeta('property', 'og:type', type);
    ensureMeta('name', 'twitter:card', imageUrl ? 'summary_large_image' : 'summary');
    ensureMeta('name', 'twitter:title', resolvedTitle);
    ensureMeta('name', 'twitter:description', description);

    if (imageUrl) {
      ensureMeta('property', 'og:image', imageUrl);
      ensureMeta('name', 'twitter:image', imageUrl);
    } else {
      removeMeta('property', 'og:image');
      removeMeta('name', 'twitter:image');
    }

    let canonical = document.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    if (!canonical) {
      canonical = document.createElement('link');
      canonical.rel = 'canonical';
      document.head.appendChild(canonical);
    }
    canonical.href = canonicalUrl;

    const existingJsonLd = document.getElementById('styledash-seo-jsonld');
    existingJsonLd?.remove();
    if (jsonLd) {
      const script = document.createElement('script');
      script.id = 'styledash-seo-jsonld';
      script.type = 'application/ld+json';
      script.text = JSON.stringify(jsonLd);
      document.head.appendChild(script);
    }

    return () => {
      document.getElementById('styledash-seo-jsonld')?.remove();
    };
  }, [title, description, image, type, jsonLd]);

  return null;
};
