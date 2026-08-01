import React, { createContext, useContext } from 'react';
import { useAuth } from './AuthContext';

interface ReferralContextType {
  referralCode: string;
  walletBalance: number;
  shareReferral: () => void;
}

const ReferralContext = createContext<ReferralContextType | undefined>(undefined);

export const ReferralProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user } = useAuth();
  const referralCode = user ? user.referralCode : 'STYLE100';
  const walletBalance = user ? user.walletBalance : 100;

  const shareReferral = () => {
    const text = `Join StyleDash and get ₹100 off your first fashion order! Use code ${referralCode}`;
    if (navigator.share) {
      navigator.share({ title: 'StyleDash Referral', text, url: window.location.origin }).catch(() => {});
    } else {
      navigator.clipboard.writeText(text);
    }
  };

  return (
    <ReferralContext.Provider value={{ referralCode, walletBalance, shareReferral }}>
      {children}
    </ReferralContext.Provider>
  );
};

export const useReferral = () => {
  const context = useContext(ReferralContext);
  if (!context) throw new Error('useReferral must be used within ReferralProvider');
  return context;
};
