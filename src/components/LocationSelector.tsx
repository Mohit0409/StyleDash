import React, { useEffect, useState } from 'react';
import { X, MapPin, CheckCircle2, AlertCircle } from 'lucide-react';
import { serviceAreaRepository } from '../repositories/serviceAreaRepository';
import { CONFIG } from '../config';
import { ServiceArea } from '../types';

type CheckState = 'idle' | 'checking' | 'serviceable' | 'unserviceable' | 'invalid' | 'unavailable';

export const LocationSelector: React.FC<{ isOpen: boolean; onClose: () => void }> = ({ isOpen, onClose }) => {
  const [pincode, setPincode] = useState(CONFIG.DEFAULT_PINCODE);
  const [result, setResult] = useState<ServiceArea | null>(null);
  const [checkState, setCheckState] = useState<CheckState>('idle');

  useEffect(() => {
    if (!isOpen) return undefined;
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleCheck = async (e: React.FormEvent) => {
    e.preventDefault();
    const normalized = pincode.trim();
    if (!/^\d{6}$/.test(normalized)) {
      setResult(null);
      setCheckState('invalid');
      return;
    }
    setCheckState('checking');
    try {
      const res = await serviceAreaRepository.checkPincode(normalized);
      setResult(res);
      setCheckState(res.serviceable ? 'serviceable' : 'unserviceable');
    } catch {
      setResult(null);
      setCheckState('unavailable');
    }
  };

  const handlePincodeChange = (value: string) => {
    setPincode(value.replace(/\D/g, '').slice(0, 6));
    setResult(null);
    setCheckState('idle');
  };

  const showResult = checkState !== 'idle' && checkState !== 'checking';
  const isSuccess = checkState === 'serviceable';
  const isProblem = checkState === 'unserviceable' || checkState === 'invalid' || checkState === 'unavailable';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div role="dialog" aria-modal="true" aria-labelledby="location-dialog-title" className="bg-white dark:bg-neutral-900 rounded-3xl max-w-md w-full p-6 shadow-2xl border border-neutral-200 dark:border-neutral-800 relative">
        <button aria-label="Close delivery availability dialog" onClick={onClose} className="absolute top-4 right-4 p-2 rounded-full hover:bg-neutral-100 dark:hover:bg-neutral-800">
          <X className="w-5 h-5 text-neutral-500" />
        </button>

        <div className="flex items-center gap-2 mb-2 text-lime-600 dark:text-lime-400 font-extrabold text-sm">
          <MapPin className="w-5 h-5" /> Hyperlocal Delivery Check
        </div>

        <h3 id="location-dialog-title" className="text-lg font-black text-neutral-900 dark:text-white mb-2">Check Delivery Availability</h3>
        <p className="text-xs text-neutral-500 mb-6">Enter your 6-digit area pincode in {CONFIG.SERVICE_CITY} to check local delivery availability.</p>

        <form onSubmit={handleCheck} className="flex gap-2 mb-4">
          <input
            type="text"
            aria-label="Delivery pincode"
            inputMode="numeric"
            pattern="[0-9]*"
            maxLength={6}
            value={pincode}
            onChange={(e) => handlePincodeChange(e.target.value)}
            placeholder="e.g. 458441"
            className="flex-1 px-4 py-2.5 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-neutral-50 dark:bg-neutral-800 text-sm font-bold text-neutral-900 dark:text-white"
          />
          <button
            type="submit"
            disabled={checkState === 'checking'}
            className="px-5 py-2.5 bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 font-bold text-xs rounded-xl disabled:cursor-not-allowed disabled:opacity-60"
          >
            {checkState === 'checking' ? 'Checking' : 'Check'}
          </button>
        </form>

        {showResult && (
          <div className={`p-4 rounded-2xl text-xs flex items-start gap-3 ${
            isSuccess
              ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-900 dark:text-emerald-200 border border-emerald-200 dark:border-emerald-800'
              : 'bg-rose-50 dark:bg-rose-950/40 text-rose-900 dark:text-rose-200 border border-rose-200 dark:border-rose-800'
          }`}>
            {isSuccess ? <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" /> : <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0" />}
            <div>
              <p className="font-bold">
                {isSuccess && result?.city ? `Serviceable in ${result.city}` : null}
                {checkState === 'unserviceable' ? 'Pincode Currently Unserviceable' : null}
                {checkState === 'invalid' ? 'Enter a Valid 6-Digit Pincode' : null}
                {checkState === 'unavailable' ? 'Could Not Check Availability' : null}
              </p>
              <p className="mt-0.5">
                {isSuccess
                  ? result?.expressAvailable && result?.estimatedDeliveryMinutes
                    ? `Local delivery is available. Express Local Delivery is also available within ${result.estimatedDeliveryMinutes} minutes.`
                    : 'Local delivery is available. Express Local Delivery is unavailable Monday–Friday.'
                  : null}
                {isProblem && checkState === 'unserviceable' ? 'We are not delivering to this pincode yet.' : null}
                {isProblem && checkState === 'invalid' ? 'Pincodes must contain exactly six numbers.' : null}
                {isProblem && checkState === 'unavailable' ? 'Please retry in a moment. We will not confirm delivery until the server check succeeds.' : null}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
