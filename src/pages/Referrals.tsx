import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { Gift, Share2, Copy, Check, Wallet, Users } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useReferral, REFERRAL_REWARDS } from '../context/ReferralContext'
import { useToast } from '../context/ToastContext'

const Referrals: React.FC = () => {
  const { user } = useAuth()
  const navigate = useNavigate()
  const { myCode, walletCredits, shareCode, redeemCode } = useReferral()
  const { showToast } = useToast()
  const [inputCode, setInputCode] = useState('')
  const [copied, setCopied] = useState(false)

  if (!user) {
    return (
      <div className="max-w-sm mx-auto px-4 py-16 text-center">
        <Gift size={40} className="text-brand-yellow mx-auto mb-3" />
        <h1 className="text-xl font-black text-gray-900 dark:text-white mb-2">Sign in to refer friends</h1>
        <p className="text-sm text-gray-400 mb-5">Earn ₹{REFERRAL_REWARDS.referrer} for every friend who joins Neemuch Blink</p>
        <button onClick={() => navigate('/profile')} className="bg-brand-yellow text-brand-dark font-bold px-5 py-2.5 rounded-xl">
          Sign In
        </button>
      </div>
    )
  }

  const shareText = `Use my code ${myCode} on Neemuch Blink and get ₹${REFERRAL_REWARDS.referee} off your first order! 🛵`

  const copyCode = async () => {
    if (!myCode) return
    try {
      await navigator.clipboard.writeText(myCode)
      setCopied(true)
      shareCode()
      showToast('Code copied!', 'success')
      setTimeout(() => setCopied(false), 2000)
    } catch {
      showToast('Could not copy — copy it manually', 'error')
    }
  }

  const handleShare = async () => {
    shareCode()
    if (navigator.share) {
      try {
        await navigator.share({ title: 'Neemuch Blink', text: shareText })
      } catch { /* user cancelled share sheet — not an error */ }
    } else {
      await copyCode()
    }
  }

  const handleRedeem = () => {
    const result = redeemCode(inputCode)
    showToast(result.message, result.success ? 'success' : 'error')
    if (result.success) setInputCode('')
  }

  return (
    <div className="max-w-lg mx-auto px-4 py-8">
      <div className="flex items-center gap-2 mb-6">
        <Gift size={20} className="text-brand-yellow" />
        <h1 className="text-2xl font-black text-gray-900 dark:text-white">Refer & Earn</h1>
      </div>

      {/* Hero card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-gradient-to-br from-brand-yellow to-brand-green rounded-3xl p-6 text-white mb-6"
      >
        <p className="text-sm font-semibold text-white/90 mb-1">Give ₹{REFERRAL_REWARDS.referrer}, Get ₹{REFERRAL_REWARDS.referee}</p>
        <h2 className="text-2xl font-black mb-3">Invite friends in Neemuch</h2>
        <p className="text-sm text-white/85 leading-relaxed mb-5">
          Share your code. When a friend places their first order, you both get wallet credit instantly.
        </p>

        {/* Code box */}
        <div className="bg-white/95 rounded-2xl p-4 flex items-center justify-between mb-3">
          <div>
            <p className="text-[10px] text-gray-400 font-bold uppercase tracking-wide">Your Code</p>
            <p className="text-xl font-black text-brand-dark tracking-wider">{myCode}</p>
          </div>
          <button onClick={copyCode} className="w-10 h-10 rounded-xl bg-brand-yellow flex items-center justify-center text-brand-dark hover:bg-yellow-400 transition-colors">
            {copied ? <Check size={16} /> : <Copy size={16} />}
          </button>
        </div>

        <button
          onClick={handleShare}
          className="w-full flex items-center justify-center gap-2 bg-brand-dark text-white font-bold py-3 rounded-xl hover:bg-gray-800 transition-colors"
        >
          <Share2 size={15} /> Share with Friends
        </button>
      </motion.div>

      {/* Wallet */}
      <div className="bg-white dark:bg-gray-800 rounded-2xl p-5 border border-gray-100 dark:border-gray-700 mb-6 flex items-center gap-4">
        <div className="w-12 h-12 bg-brand-green/10 rounded-xl flex items-center justify-center flex-shrink-0">
          <Wallet size={22} className="text-brand-green" />
        </div>
        <div>
          <p className="text-xs text-gray-400">Wallet Balance</p>
          <p className="text-2xl font-black text-gray-900 dark:text-white">₹{walletCredits}</p>
        </div>
      </div>

      {/* Redeem a code */}
      <div className="bg-white dark:bg-gray-800 rounded-2xl p-5 border border-gray-100 dark:border-gray-700 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <Users size={16} className="text-blue-500" />
          <h3 className="font-bold text-gray-900 dark:text-white">Have a friend's code?</h3>
        </div>
        <div className="flex gap-2">
          <input
            value={inputCode}
            onChange={e => setInputCode(e.target.value.toUpperCase())}
            placeholder="Enter referral code"
            className="flex-1 text-sm bg-gray-100 dark:bg-gray-700 rounded-xl px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-yellow dark:text-white"
          />
          <button
            onClick={handleRedeem}
            className="bg-brand-green text-white font-bold text-sm px-4 py-2.5 rounded-xl hover:bg-green-600 transition-colors"
          >
            Redeem
          </button>
        </div>
        <p className="text-xs text-gray-400 mt-2">Get ₹{REFERRAL_REWARDS.referee} credited instantly on your first order.</p>
      </div>

      {/* How it works */}
      <div className="bg-gray-50 dark:bg-gray-800/50 rounded-2xl p-5">
        <h3 className="font-bold text-gray-900 dark:text-white mb-3 text-sm">How it works</h3>
        <ul className="space-y-2 text-sm text-gray-600 dark:text-gray-300">
          <li className="flex gap-2"><span>1.</span><span>Share your code with friends in Neemuch</span></li>
          <li className="flex gap-2"><span>2.</span><span>They sign up and place their first order</span></li>
          <li className="flex gap-2"><span>3.</span><span>You both get wallet credit — no limit on referrals</span></li>
        </ul>
      </div>
    </div>
  )
}

export default Referrals
