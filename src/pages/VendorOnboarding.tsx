import React, { useState } from 'react';
import { Store, CheckCircle2, ArrowRight } from 'lucide-react';
import { SEO } from '../components/SEO';
import { vendorApplicationApi } from '../services/businessApi';
import { useToast } from '../context/ToastContext';
import { CONFIG } from '../config';

export const VendorOnboarding: React.FC = () => {
  const { showToast } = useToast();
  const [submitted, setSubmitted] = useState(false);

  const [storeName, setStoreName] = useState('');
  const [ownerName, setOwnerName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [category, setCategory] = useState<'Clothing & Fashion' | 'Footwear' | 'Electronics' | 'Home & Living' | 'General Store'>('Clothing & Fashion');
  const [address, setAddress] = useState('');
  const [description, setDescription] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await vendorApplicationApi.submit({
      storeName,
      ownerName,
      email,
      phone,
      category,
      address,
      description,
      pincode: CONFIG.DEFAULT_PINCODE,
    });
    setSubmitted(true);
    showToast('Application submitted! Our Neemuch team will contact you shortly.', 'success');
  };

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <SEO title="Partner Store Onboarding - StyleDash" />

      <div className="text-center space-y-2">
        <div className="w-16 h-16 bg-lime-400 text-neutral-950 rounded-3xl flex items-center justify-center mx-auto shadow-xl">
          <Store className="w-8 h-8" />
        </div>
        <h1 className="text-2xl sm:text-3xl font-black text-neutral-900 dark:text-white">Partner & List Your Local Store</h1>
        <p className="text-xs text-neutral-500 max-w-lg mx-auto">
          Are you a shopkeeper in Neemuch? Sell your fashion, clothing, or retail inventory on StyleDash and reach thousands of local customers with 60-minute delivery!
        </p>
      </div>

      {submitted ? (
        <div className="p-8 bg-white dark:bg-neutral-900 rounded-3xl border border-neutral-200 dark:border-neutral-800 text-center space-y-4 shadow-sm">
          <CheckCircle2 className="w-12 h-12 text-emerald-500 mx-auto" />
          <h3 className="text-xl font-black text-neutral-900 dark:text-white">Store Registration Submitted!</h3>
          <p className="text-xs text-neutral-500 max-w-md mx-auto">
            Thank you, <strong>{ownerName}</strong>. Your store application for <strong>{storeName}</strong> has been registered. Our Neemuch city partner team will review your application and assist you in uploading your product inventory data.
          </p>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="p-6 sm:p-8 bg-white dark:bg-neutral-900 rounded-3xl border border-neutral-200 dark:border-neutral-800 space-y-6 shadow-sm">
          <h3 className="font-extrabold text-base text-neutral-900 dark:text-white border-b border-neutral-100 dark:border-neutral-800 pb-3">
            Store Registration & Inventory Submission Form
          </h3>

          <div className="grid sm:grid-cols-2 gap-4 text-xs">
            <div>
              <label className="block font-bold text-neutral-700 dark:text-neutral-300 mb-1">Store / Shop Name</label>
              <input
                required
                type="text"
                placeholder="e.g. Royal Fashion Boutique"
                value={storeName}
                onChange={(e) => setStoreName(e.target.value)}
                className="w-full p-2.5 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 font-bold"
              />
            </div>

            <div>
              <label className="block font-bold text-neutral-700 dark:text-neutral-300 mb-1">Owner Name</label>
              <input
                required
                type="text"
                placeholder="e.g. Ramesh Kumar"
                value={ownerName}
                onChange={(e) => setOwnerName(e.target.value)}
                className="w-full p-2.5 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 font-bold"
              />
            </div>

            <div>
              <label className="block font-bold text-neutral-700 dark:text-neutral-300 mb-1">Phone Number</label>
              <input
                required
                type="text"
                placeholder="+91 9876543210"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="w-full p-2.5 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 font-bold"
              />
            </div>

            <div>
              <label className="block font-bold text-neutral-700 dark:text-neutral-300 mb-1">Email Address</label>
              <input
                required
                type="email"
                placeholder="store@neemuch.in"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full p-2.5 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 font-bold"
              />
            </div>

            <div>
              <label className="block font-bold text-neutral-700 dark:text-neutral-300 mb-1">Store Category</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value as any)}
                className="w-full p-2.5 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 font-bold"
              >
                <option value="Clothing & Fashion">Clothing & Fashion</option>
                <option value="Footwear">Footwear</option>
                <option value="Electronics">Electronics</option>
                <option value="Home & Living">Home & Living</option>
                <option value="General Store">General Store</option>
              </select>
            </div>

            <div>
              <label className="block font-bold text-neutral-700 dark:text-neutral-300 mb-1">Shop Address in Neemuch</label>
              <input
                required
                type="text"
                placeholder="e.g. 45 Main Market, Neemuch"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                className="w-full p-2.5 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 font-bold"
              />
            </div>

            <div className="sm:col-span-2">
              <label className="block font-bold text-neutral-700 dark:text-neutral-300 mb-1">Store Description & Goods Data Overview</label>
              <textarea
                required
                rows={3}
                placeholder="Describe your store inventory (e.g. sarees, jeans, shoes, brands carried, total SKUs)..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full p-2.5 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 font-bold"
              />
            </div>
          </div>

          <button
            type="submit"
            className="w-full py-3.5 bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 font-black text-xs uppercase tracking-wider rounded-xl shadow-lg hover:bg-neutral-800 dark:hover:bg-lime-300 transition-colors flex items-center justify-center gap-2"
          >
            <span>Submit Store Application</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>
      )}
    </div>
  );
};
