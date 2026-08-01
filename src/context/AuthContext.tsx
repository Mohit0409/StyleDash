import React, { createContext, useContext, useState } from 'react'
import type { User } from '../types'
import { identifyUser } from '../firebase/analytics'

interface AuthContextType {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  isAdmin: boolean
}

const AuthContext = createContext<AuthContextType | null>(null)

export const useAuth = () => {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

// Demo admin email
const ADMIN_EMAIL = 'admin@neemuchblink.in'

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(() => {
    try {
      const saved = localStorage.getItem('nb-user')
      return saved ? JSON.parse(saved) : null
    } catch { return null }
  })
  const [loading, setLoading] = useState(false)

  const login = async (email: string, _password: string) => {
    setLoading(true)
    // Simulate auth — replace with Firebase Auth
    await new Promise(r => setTimeout(r, 800))
    const mockUser: User = {
      uid: '1',
      name: email === ADMIN_EMAIL ? 'Admin User' : 'Demo User',
      email,
      photoURL: `https://api.dicebear.com/7.x/initials/svg?seed=${email}`,
    }
    setUser(mockUser)
    localStorage.setItem('nb-user', JSON.stringify(mockUser))
    identifyUser(mockUser.uid, email === ADMIN_EMAIL)
    setLoading(false)
  }

  const logout = () => {
    setUser(null)
    localStorage.removeItem('nb-user')
  }

  const isAdmin = user?.email === ADMIN_EMAIL

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, isAdmin }}>
      {children}
    </AuthContext.Provider>
  )
}
