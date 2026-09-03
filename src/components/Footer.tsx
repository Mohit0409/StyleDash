import React from 'react';
import { Link } from 'react-router-dom';
import { ShieldCheck, Truck, RefreshCw, Zap } from 'lucide-react';
import { CONFIG } from '../config';
import { BrandWordmark } from './BrandWordmark';

export const Footer: React.FC = () => {
  return (
    <footer className="bg-neutral-950 text-neutral-300 border-t border-neutral-800 pt-12 pb-8 mt-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">

        {/* Trust Badges */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 pb-12 border-b border-neutral-800 text-center">
          <div className="flex flex-col items-center gap-2">
            <div className="p-3 bg-neutral-900 rounded-full text-lime-400">
              <Zap className="w-6 h-6 fill-lime-400" />
            </div>
            <h4 className="font-bold text-white text-sm">Local Delivery</h4>
            <p className="text-xs text-neutral-400">
              Hyperlocal fashion dispatch in {CONFIG.SERVICE_CITY}
            </p>
          </div>
          <div className="flex flex-col items-center gap-2">
            <div className="p-3 bg-neutral-900 rounded-full text-lime-400">
              <RefreshCw className="w-6 h-6" />
            </div>
            <h4 className="font-bold text-white text-sm">
              {CONFIG.LEGAL.EXCHANGE_WINDOW_DAYS}-Day Size Exchange
            </h4>
            <p className="text-xs text-neutral-400">
              Eligible items; conditions and pickup charges apply
            </p>
          </div>
          <div className="flex flex-col items-center gap-2">
            <div className="p-3 bg-neutral-900 rounded-full text-lime-400">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <h4 className="font-bold text-white text-sm">Local Selection</h4>
            <p className="text-xs text-neutral-400">
              Listings from participating local stores
            </p>
          </div>
          <div className="flex flex-col items-center gap-2">
            <div className="p-3 bg-neutral-900 rounded-full text-lime-400">
              <Truck className="w-6 h-6" />
            </div>
            <h4 className="font-bold text-white text-sm">Free Shipping</h4>
            <p className="text-xs text-neutral-400">
              On eligible orders above INR {CONFIG.FREE_DELIVERY_THRESHOLD}
            </p>
          </div>
        </div>

        {/* Footer Nav Links */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-8 py-10">
          <div className="col-span-2">
            <div className="mb-3 w-44 max-w-full">
              <BrandWordmark inverse />
            </div>
            <p className="text-xs text-neutral-400 mb-4 max-w-sm">
              Vibe4You provides hyperlocal fashion ordering and delivery in its
              currently supported Neemuch service area.
            </p>
            <p className="text-xs text-neutral-500 mb-1">
              Service Area: {CONFIG.SERVICE_CITY}, MP ({CONFIG.DEFAULT_PINCODE})
            </p>
            <p className="text-xs text-neutral-500">
              Support: {CONFIG.LEGAL.SUPPORT_PHONE} | {CONFIG.LEGAL.SUPPORT_EMAIL}
            </p>
          </div>

          <div>
            <h5 className="font-bold text-white text-sm mb-3">Shop Departments</h5>
            <ul className="space-y-2 text-xs">
              <li><Link to="/products?dept=men" className="hover:text-lime-400">Men&apos;s Fashion</Link></li>
              <li><Link to="/products?dept=women" className="hover:text-lime-400">Women&apos;s Clothing</Link></li>
              <li><Link to="/products?dept=kids" className="hover:text-lime-400">Kids Wear</Link></li>
              <li><Link to="/products?category=Footwear" className="hover:text-lime-400">Footwear Spotlight</Link></li>
              <li><Link to="/products?category=Accessories" className="hover:text-lime-400">Accessories &amp; Bags</Link></li>
              <li><Link to="/products?category=Beauty%20%26%20Personal%20Care" className="hover:text-lime-400">Beauty &amp; Personal Care</Link></li>
            </ul>
          </div>

          <div>
            <h5 className="font-bold text-white text-sm mb-3">Customer Service</h5>
            <ul className="space-y-2 text-xs">
              <li><Link to="/help" className="hover:text-lime-400">Help &amp; Support</Link></li>
              <li><Link to="/returns" className="hover:text-lime-400">Returns &amp; Size Exchange</Link></li>
              <li><Link to="/privacy" className="hover:text-lime-400">Privacy Policy</Link></li>
              <li><Link to="/terms" className="hover:text-lime-400">Terms of Service</Link></li>
            </ul>
          </div>

          <div>
            <h5 className="font-bold text-white text-sm mb-3">Your Account</h5>
            <ul className="space-y-2 text-xs">
              <li><Link to="/profile" className="hover:text-lime-400">My Profile</Link></li>
              <li><Link to="/orders" className="hover:text-lime-400">Order History</Link></li>
              <li><Link to="/wishlist" className="hover:text-lime-400">Saved Wishlist</Link></li>
            </ul>
          </div>
        </div>

        {/* Bottom copyright */}
        <div className="pt-6 border-t border-neutral-900 flex flex-col md:flex-row items-center justify-between text-xs text-neutral-500 gap-4">
          <p>
            Copyright 2026 Vibe4You. Operated by {CONFIG.LEGAL.PROPRIETOR_NAME}. All rights reserved.
          </p>
          <p>
            {CONFIG.LEGAL.ADDRESS}
          </p>
        </div>
      </div>
    </footer>
  );
};
