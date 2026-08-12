import React, { useEffect } from 'react';

interface SEOProps {
  title?: string;
  description?: string;
}

export const SEO: React.FC<SEOProps> = ({
  title = 'StyleDash - Your look, delivered fast.',
  description = 'Fashion essentials, trending streetwear, ethnic wear, and footwear delivered from nearby stores in Neemuch within 60 minutes.'
}) => {
  useEffect(() => {
    document.title = title.includes('StyleDash') ? title : `${title} | StyleDash`;
    const metaDesc = document.querySelector('meta[name="description"]');
    if (metaDesc) {
      metaDesc.setAttribute('content', description);
    }
  }, [title, description]);

  return null;
};
