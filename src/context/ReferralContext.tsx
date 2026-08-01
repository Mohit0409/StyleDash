import React, { createContext, useContext, useState, useEffect } from 'react'
import { useAuth } from './AuthContext'
import { trackReferralShared, trackReferralRedeemed } from '../firebase/analytics'

const REWARD_FOR_REFERRER = 50
const REWARD_FOR_REFEREE = 50

interface ReferralContextType {
  myCode: string | null
  redeemedCodes: string[]
  walletCredits: number
  shareCode: () => void
  redeemCode: (code: string) => { success: boolean; message: string }
}

const ReferralContext = createContext<ReferralContextType | null>(null)

export const useReferral = () => {
  const ctx = useContext(ReferralContext)
  if (!ctx) throw new Error('useReferral must be used within ReferralProvider')
  return ctx
}

const generateCode = (uid: string) => `NB${uid.slice(0, 4).toUpperCase()}${Math.floor(Math.random() * 900 + 100)}`

export const ReferralProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user } = useAuth()
  const [myCode, setMyCode] = useState<string | null>(null)
  const [redeemedCodes, setRedeemedCodes] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem('nb-redeemed-codes')
      return saved ? JSON.parse(saved) : []
    } catch { return [] }
  })
  const [walletCredits, setWalletCredits] = useState<number>(() => {
    try {
      const saved = localStorage.getItem('nb-wallet-credits')
      return saved ? Number(saved) : 0
    } catch { return 0 }
  })

  // Generate (and persist) a stable referral code per logged-in user
  useEffect(() => {
    if (!user) { setMyCode(null); return }
    try {
      const key = `nb-referral-code-${user.uid}`
      const saved = localStorage.getItem(key)
      if (saved) {
        setMyCode(saved)
      } else {
        const code = generateCode(user.uid)
        localStorage.setItem(key, code)
        setMyCode(code)
      }
    } catch {
      setMyCode(generateCode(user.uid))
    }
  }, [user])

  useEffect(() => {
    localStorage.setItem('nb-redeemed-codes', JSON.stringify(redeemedCodes))
  }, [redeemedCodes])

  useEffect(() => {
    localStorage.setItem('nb-wallet-credits', String(walletCredits))
  }, [walletCredits])

  const shareCode = () => {
    if (!myCode) return
    trackReferralShared(myCode)
  }

  const redeemCode = (code: string): { success: boolean; message: string } => {
    const trimmed = code.trim().toUpperCase()
    if (!trimmed) return { success: false, message: 'Enter a referral code' }
    if (trimmed === myCode) return { success: false, message: "You can't use your own code" }
    if (redeemedCodes.includes(trimmed)) return { success: false, message: 'You\'ve already used a referral code' }

    // In production this would validate against Firestore and credit both
    // users server-side. Here we credit the referee (current user) locally
    // and log the event — the referrer's side would be credited by a
    // Cloud Function trigger watching the `referrals` collection.
    setRedeemedCodes(prev => [...prev, trimmed])
    setWalletCredits(prev => prev + REWARD_FOR_REFEREE)
    trackReferralRedeemed(trimmed, REWARD_FOR_REFEREE)
    return { success: true, message: `₹${REWARD_FOR_REFEREE} credited to your wallet!` }
  }

  return (
    <ReferralContext.Provider value={{ myCode, redeemedCodes, walletCredits, shareCode, redeemCode }}>
      {children}
    </ReferralContext.Provider>
  )
}

export const REFERRAL_REWARDS = { referrer: REWARD_FOR_REFERRER, referee: REWARD_FOR_REFEREE }
