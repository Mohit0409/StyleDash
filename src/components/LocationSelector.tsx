import React, { useState } from 'react';
import { X, MapPin, CheckCircle2, AlertCircle } from 'lucide-react';
import { serviceAreaRepository } from '../repositories/serviceAreaRepository';
import { CONFIG } from '../config';

export const LocationSelector: React.FC<{ isOpen: boolean; onClose: () => void }> = ({ isOpen, onClose }) => {
  const [pincode, setPincode] = useState(CONFIG.DEFAULT_PINCODE);
  const [result, setResult] = useState<any>(null);

  if (!isOpen) return null;

  const handleCheck = async (e: React.FormEvent) => {
    e.preventDefault();
    const res = await serviceAreaRepository.checkPincode(pincode);
    setResult(res);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-white dark:bg-neutral-900 rounded-3xl max-w-md w-full p-6 shadow-2xl border border-neutral-200 dark:border-neutral-800 relative">
        <button onClick={onClose} className="absolute top-4 right-4 p-2 rounded-full hover:bg-neutral-100 dark:hover:bg-neutral-800">
          <X className="w-5 h-5 text-neutral-500" />
        </button>

        <div className="flex items-center gap-2 mb-2 text-lime-600 dark:text-lime-400 font-extrabold text-sm">
          <MapPin className="w-5 h-5" /> Hyperlocal Delivery Check
        </div>

        <h3 className="text-lg font-black text-neutral-900 dark:text-white mb-2">Check Delivery Availability</h3>
        <p className="text-xs text-neutral-500 mb-6">Enter your 6-digit area pincode in {CONFIG.SERVICE_CITY} to verify 60-minute express service.</p>

        <form onSubmit={handleCheck} className="flex gap-2 mb-4">
          <input
            type="text"
            maxLength={6}
            value={pincode}
            onChange={(e) => setPincode(e.target.value)}
            placeholder="e.g. 458441"
            className="flex-1 px-4 py-2.5 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 text-sm font-bold text-neutral-900 dark:text-white"
          />
          <button type="submit" className="px-5 py-2.5 bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 font-bold text-xs rounded-xl">
            Check
          </button>
        </form>

        {result && (
          <div className={`p-4 rounded-2xl text-xs flex items-start gap-3 ${
            result.serviceable
              ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-900 dark:text-emerald-200 border border-emerald-200 dark:border-emerald-800'
              : 'bg-rose-50 dark:bg-rose-950/40 text-rose-900 dark:text-rose-200 border border-rose-200 dark:border-rose-800'
          }`}>
            {result.serviceable ? <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" /> : <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0" />}
            <div>
              <p className="font-bold">{result.serviceable ? `Serviceable in ${result.city}` : 'Pincode Currently Unserviceable'}</p>
              <p className="mt-0.5">
                {result.serviceable
                  ? `Express fashion delivery available within ${result.estimatedDeliveryMinutes} minutes!`
                  : 'We are expanding rapidly across Madhya Pradesh. Try pincode 458441 for Neemuch.'}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
