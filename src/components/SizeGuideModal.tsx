import React, { useState } from 'react';
import { X, Check } from 'lucide-react';

export const SizeGuideModal: React.FC<{ isOpen: boolean; onClose: () => void; department: string }> = ({
  isOpen,
  onClose,
  department
}) => {
  const [tab, setTab] = useState<'apparel' | 'footwear'>('apparel');

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-white dark:bg-neutral-900 rounded-3xl max-w-2xl w-full p-6 shadow-2xl border border-neutral-200 dark:border-neutral-800 relative max-h-[90vh] overflow-y-auto">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-2 rounded-full hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-500"
        >
          <X className="w-5 h-5" />
        </button>

        <h3 className="text-xl font-black text-neutral-900 dark:text-white mb-2">StyleDash Size Guide</h3>
        <p className="text-xs text-neutral-500 mb-6">Find your perfect fit before ordering for 60-minute doorstep delivery.</p>

        {/* Category Tabs */}
        <div className="flex gap-3 mb-6 border-b border-neutral-200 dark:border-neutral-800">
          <button
            onClick={() => setTab('apparel')}
            className={`pb-2 text-xs font-extrabold uppercase border-b-2 transition-colors ${
              tab === 'apparel' ? 'border-lime-500 text-lime-600 dark:text-lime-400' : 'border-transparent text-neutral-400'
            }`}
          >
            Apparel (Chest & Waist in inches)
          </button>
          <button
            onClick={() => setTab('footwear')}
            className={`pb-2 text-xs font-extrabold uppercase border-b-2 transition-colors ${
              tab === 'footwear' ? 'border-lime-500 text-lime-600 dark:text-lime-400' : 'border-transparent text-neutral-400'
            }`}
          >
            Footwear (UK / India Size)
          </button>
        </div>

        {tab === 'apparel' ? (
          <table className="w-full text-xs text-left text-neutral-700 dark:text-neutral-300 border-collapse">
            <thead>
              <tr className="bg-neutral-100 dark:bg-neutral-800 text-neutral-900 dark:text-white font-extrabold">
                <th className="p-3 rounded-l-lg">Size Tag</th>
                <th className="p-3">Chest (in)</th>
                <th className="p-3">Waist (in)</th>
                <th className="p-3 rounded-r-lg">Shoulder (in)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100 dark:divide-neutral-800">
              <tr><td className="p-3 font-bold">S</td><td className="p-3">36 - 38</td><td className="p-3">28 - 30</td><td className="p-3">16.5</td></tr>
              <tr><td className="p-3 font-bold">M</td><td className="p-3">38 - 40</td><td className="p-3">31 - 33</td><td className="p-3">17.5</td></tr>
              <tr><td className="p-3 font-bold">L</td><td className="p-3">40 - 42</td><td className="p-3">34 - 36</td><td className="p-3">18.5</td></tr>
              <tr><td className="p-3 font-bold">XL</td><td className="p-3">42 - 44</td><td className="p-3">37 - 39</td><td className="p-3">19.5</td></tr>
              <tr><td className="p-3 font-bold">XXL</td><td className="p-3">44 - 46</td><td className="p-3">40 - 42</td><td className="p-3">20.5</td></tr>
            </tbody>
          </table>
        ) : (
          <table className="w-full text-xs text-left text-neutral-700 dark:text-neutral-300 border-collapse">
            <thead>
              <tr className="bg-neutral-100 dark:bg-neutral-800 text-neutral-900 dark:text-white font-extrabold">
                <th className="p-3 rounded-l-lg">UK / India</th>
                <th className="p-3">US Size</th>
                <th className="p-3">EU Size</th>
                <th className="p-3 rounded-r-lg">Foot Length (cm)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100 dark:divide-neutral-800">
              <tr><td className="p-3 font-bold">UK 6</td><td className="p-3">7</td><td className="p-3">40</td><td className="p-3">24.5</td></tr>
              <tr><td className="p-3 font-bold">UK 7</td><td className="p-3">8</td><td className="p-3">41</td><td className="p-3">25.5</td></tr>
              <tr><td className="p-3 font-bold">UK 8</td><td className="p-3">9</td><td className="p-3">42</td><td className="p-3">26.5</td></tr>
              <tr><td className="p-3 font-bold">UK 9</td><td className="p-3">10</td><td className="p-3">43</td><td className="p-3">27.5</td></tr>
              <tr><td className="p-3 font-bold">UK 10</td><td className="p-3">11</td><td className="p-3">44</td><td className="p-3">28.5</td></tr>
            </tbody>
          </table>
        )}

        <div className="mt-6 p-4 bg-neutral-50 dark:bg-neutral-800 rounded-2xl text-xs text-neutral-600 dark:text-neutral-400 space-y-1">
          <p className="font-bold text-neutral-900 dark:text-white">Need a size swap after delivery?</p>
          <p>StyleDash offers instant doorstep 7-day size exchanges in Neemuch free of cost!</p>
        </div>
      </div>
    </div>
  );
};
