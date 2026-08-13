import React from 'react';
import { Link } from 'react-router-dom';
import { ShieldCheck, Truck, RefreshCw, Zap, Heart } from 'lucide-react';
import { CONFIG } from '../config';

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
            <h4 className="font-bold text-white text-sm">60-Minute Delivery</h4>
            <p className="text-xs text-neutral-400">Hyperlocal fashion dispatch in {CONFIG.SERVICE_CITY}</p>
          </div>
          <div className="flex flex-col items-center gap-2">
            <div className="p-3 bg-neutral-900 rounded-full text-lime-400">
              <RefreshCw className="w-6 h-6" />
            </div>
            <h4 className="font-bold text-white text-sm">7-Day Easy Exchange</h4>
            <p className="text-xs text-neutral-400">Hassle-free size swaps at your doorstep</p>
          </div>
          <div className="flex flex-col items-center gap-2">
            <div className="p-3 bg-neutral-900 rounded-full text-lime-400">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <h4 className="font-bold text-white text-sm">100% Quality Checked</h4>
            <p className="text-xs text-neutral-400">Curated from top verified local stores</p>
          </div>
          <div className="flex flex-col items-center gap-2">
            <div className="p-3 bg-neutral-900 rounded-full text-lime-400">
              <Truck className="w-6 h-6" />
            </div>
            <h4 className="font-bold text-white text-sm">Free Shipping</h4>
            <p className="text-xs text-neutral-400">On all orders above ₹{CONFIG.FREE_DELIVERY_THRESHOLD}</p>
          </div>
        </div>

        {/* Footer Nav Links */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-8 py-10">
          <div className="col-span-2">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-8 h-8 bg-lime-400 text-neutral-950 font-black rounded-lg flex items-center justify-center text-lg">
                SD
              </div>
              <span className="font-extrabold text-xl text-white">Style<span className="text-lime-400">Dash</span></span>
            </div>
            <p className="text-xs text-neutral-400 mb-4 max-w-sm">
              StyleDash is Neemuch's premier clothing quick-commerce platform delivering trending street style, ethnic wear, activewear, and footwear right to your door in 60 minutes.
            </p>
            <p className="text-xs text-neutral-500">
              Service Area: {CONFIG.SERVICE_CITY}, MP ({CONFIG.DEFAULT_PINCODE})
            </p>
          </div>

          <div>
            <h5 className="font-bold text-white text-sm mb-3">Shop Departments</h5>
            <ul className="space-y-2 text-xs">
              <li><Link to="/products?dept=men" className="hover:text-lime-400">Men's Fashion</Link></li>
              <li><Link to="/products?dept=women" className="hover:text-lime-400">Women's Clothing</Link></li>
              <li><Link to="/products?dept=kids" className="hover:text-lime-400">Kids Wear</Link></li>
              <li><Link to="/products?dept=footwear" className="hover:text-lime-400">Footwear Spotlight</Link></li>
              <li><Link to="/products?dept=accessories" className="hover:text-lime-400">Accessories & Bags</Link></li>
            </ul>
          </div>

          <div>
            <h5 className="font-bold text-white text-sm mb-3">Customer Service</h5>
            <ul className="space-y-2 text-xs">
              <li><Link to="/help" className="hover:text-lime-400">Help & Support</Link></li>
              <li><Link to="/returns" className="hover:text-lime-400">Returns & Size Exchange</Link></li>
              <li><Link to="/privacy" className="hover:text-lime-400">Privacy Policy</Link></li>
              <li><Link to="/terms" className="hover:text-lime-400">Terms of Service</Link></li>
            </ul>
          </div>

          <div>
            <h5 className="font-bold text-white text-sm mb-3">Account & Admin</h5>
            <ul className="space-y-2 text-xs">
              <li><Link to="/profile" className="hover:text-lime-400">My Profile</Link></li>
              <li><Link to="/orders" className="hover:text-lime-400">Order History</Link></li>
              <li><Link to="/wishlist" className="hover:text-lime-400">Saved Wishlist</Link></li>
            </ul>
          </div>
        </div>

        {/* Bottom copyright */}
        <div className="pt-6 border-t border-neutral-900 flex flex-col md:flex-row items-center justify-between text-xs text-neutral-500 gap-4">
          <p>© 2026 StyleDash Commerce. All rights reserved.</p>
          <p className="flex items-center gap-1">
            Crafted for <span className="text-white font-medium">Neemuch Fashion</span>
          </p>
        </div>
      </div>
    </footer>
  );
};
