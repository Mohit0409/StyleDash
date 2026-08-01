import React from 'react'
import { Link } from 'react-router-dom'
import { MapPin, Phone, Mail, Instagram, Twitter, Facebook } from 'lucide-react'

const Footer: React.FC = () => (
  <footer className="bg-gray-900 text-gray-300 mt-16">
    <div className="max-w-7xl mx-auto px-4 py-12 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-8">
      {/* Brand */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <div className="w-8 h-8 bg-brand-yellow rounded-xl flex items-center justify-center font-black text-brand-dark text-sm">NB</div>
          <span className="font-extrabold text-lg text-white">Neemuch<span className="text-brand-yellow">Blink</span></span>
        </div>
        <p className="text-sm text-gray-400 leading-relaxed">Everything you need, delivered fast. Fresh groceries and daily essentials in 10–20 minutes.</p>
        <div className="flex gap-3 mt-4">
          <a href="#" className="w-8 h-8 bg-gray-800 rounded-full flex items-center justify-center hover:bg-brand-yellow hover:text-brand-dark transition-colors"><Instagram size={14} /></a>
          <a href="#" className="w-8 h-8 bg-gray-800 rounded-full flex items-center justify-center hover:bg-brand-yellow hover:text-brand-dark transition-colors"><Twitter size={14} /></a>
          <a href="#" className="w-8 h-8 bg-gray-800 rounded-full flex items-center justify-center hover:bg-brand-yellow hover:text-brand-dark transition-colors"><Facebook size={14} /></a>
        </div>
      </div>

      {/* Quick Links */}
      <div>
        <h4 className="font-bold text-white mb-3">Quick Links</h4>
        <ul className="space-y-2 text-sm">
          {[['/', 'Home'], ['/categories', 'Categories'], ['/products', 'All Products'], ['/orders', 'My Orders'], ['/profile', 'Profile']].map(([to, label]) => (
            <li key={to}><Link to={to} className="hover:text-brand-yellow transition-colors">{label}</Link></li>
          ))}
        </ul>
      </div>

      {/* Categories */}
      <div>
        <h4 className="font-bold text-white mb-3">Categories</h4>
        <ul className="space-y-2 text-sm">
          {['Vegetables', 'Fruits', 'Dairy', 'Snacks', 'Beverages'].map(c => (
            <li key={c}>
              <Link to={`/products?category=${c.toLowerCase()}`} className="hover:text-brand-yellow transition-colors">{c}</Link>
            </li>
          ))}
        </ul>
      </div>

      {/* Contact */}
      <div>
        <h4 className="font-bold text-white mb-3">Contact</h4>
        <ul className="space-y-3 text-sm">
          <li className="flex items-start gap-2">
            <MapPin size={14} className="text-brand-yellow mt-0.5 flex-shrink-0" />
            <span>Neemuch, Madhya Pradesh, India</span>
          </li>
          <li className="flex items-center gap-2">
            <Phone size={14} className="text-brand-yellow flex-shrink-0" />
            <a href="tel:+919000000000" className="hover:text-brand-yellow transition-colors">+91 90000 00000</a>
          </li>
          <li className="flex items-center gap-2">
            <Mail size={14} className="text-brand-yellow flex-shrink-0" />
            <a href="mailto:support@neemuchblink.in" className="hover:text-brand-yellow transition-colors">support@neemuchblink.in</a>
          </li>
        </ul>
        <div className="mt-4 p-3 bg-gray-800 rounded-xl">
          <p className="text-xs text-brand-yellow font-bold">⚡ Delivery Time</p>
          <p className="text-sm font-semibold text-white mt-0.5">10–20 Minutes</p>
        </div>
      </div>
    </div>
    <div className="border-t border-gray-800 py-4">
      <p className="text-center text-xs text-gray-500">© {new Date().getFullYear()} Neemuch Blink. All rights reserved. Made with ❤️ in Neemuch, MP.</p>
    </div>
  </footer>
)

export default Footer
