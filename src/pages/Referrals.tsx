import React from 'react';
import { Share2, Gift, Wallet, Copy } from 'lucide-react';
import { SEO } from '../components/SEO';
import { useReferral } from '../context/ReferralContext';
import { useToast } from '../context/ToastContext';

export const Referrals: React.FC = () => {
  const { referralCode, walletBalance, shareReferral } = useReferral();
  const { showToast } = useToast();

  const handleCopy = () => {
    navigator.clipboard.writeText(referralCode);
    showToast('Referral code copied to clipboard!', 'success');
  };

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <SEO title="Refer & Earn - StyleDash" />

      <div className="text-center space-y-2">
        <div className="w-16 h-16 bg-lime-400 text-neutral-950 rounded-3xl flex items-center justify-center mx-auto shadow-lg">
          <Gift className="w-8 h-8" />
        </div>
        <h1 className="text-2xl sm:text-3xl font-black text-neutral-900 dark:text-white">Give ₹100, Get ₹100</h1>
        <p className="text-xs text-neutral-500 max-w-md mx-auto">
          Share your referral code with friends in Neemuch. When they place their first fashion order, both of you earn ₹100 in StyleWallet credits.
        </p>
      </div>

      <div className="p-6 bg-white dark:bg-neutral-900 rounded-3xl border border-neutral-200 dark:border-neutral-800 text-center space-y-4 shadow-sm">
        <span className="text-xs font-bold text-neutral-400 uppercase">Your Unique Invite Code</span>
        <div className="flex items-center justify-center gap-3 p-3 bg-neutral-50 dark:bg-neutral-800 rounded-2xl border border-neutral-200 dark:border-neutral-700 max-w-xs mx-auto">
          <span className="font-black text-xl text-neutral-900 dark:text-white tracking-wider">{referralCode}</span>
          <button onClick={handleCopy} className="p-2 hover:bg-neutral-200 dark:hover:bg-neutral-700 rounded-xl text-neutral-600 dark:text-neutral-300">
            <Copy className="w-4 h-4" />
          </button>
        </div>

        <button
          onClick={shareReferral}
          className="w-full py-3.5 bg-neutral-950 dark:bg-lime-400 text-white dark:text-neutral-950 font-black text-xs uppercase tracking-wider rounded-xl shadow-lg hover:bg-neutral-800 dark:hover:bg-lime-300 transition-colors"
        >
          Share Referral Link
        </button>
      </div>

      <div className="p-6 bg-lime-50 dark:bg-lime-950/20 rounded-3xl border border-lime-200 dark:border-lime-900 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Wallet className="w-6 h-6 text-lime-600" />
          <div>
            <span className="text-xs font-bold text-neutral-500">Your StyleWallet Balance</span>
            <h4 className="text-xl font-black text-neutral-900 dark:text-white">₹{walletBalance}</h4>
          </div>
        </div>
        <span className="text-xs font-bold text-lime-700 dark:text-lime-300">Auto-applies at Checkout</span>
      </div>
    </div>
  );
};
