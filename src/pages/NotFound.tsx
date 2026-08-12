import React from 'react';
import { Link } from 'react-router-dom';

export const NotFound: React.FC = () => {
  return (
    <div className="max-w-md mx-auto py-24 text-center space-y-4">
      <h1 className="text-6xl font-black text-neutral-900 dark:text-white">404</h1>
      <h2 className="text-xl font-bold">Page Not Found</h2>
      <p className="text-xs text-neutral-500">The fashion route you requested does not exist on StyleDash.</p>
      <Link to="/" className="inline-block px-6 py-2.5 bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 font-bold text-xs rounded-xl">
        Return to Home
      </Link>
    </div>
  );
};
