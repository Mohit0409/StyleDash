import React, { createContext, useContext, useState, useEffect } from 'react'
import type { Product } from '../types'

interface WishlistContextType {
  items: Product[]
  toggle: (product: Product) => void
  has: (productId: string) => boolean
}

const WishlistContext = createContext<WishlistContextType | null>(null)

export const useWishlist = () => {
  const ctx = useContext(WishlistContext)
  if (!ctx) throw new Error('useWishlist must be used within WishlistProvider')
  return ctx
}

export const WishlistProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [items, setItems] = useState<Product[]>(() => {
    try {
      const saved = localStorage.getItem('nb-wishlist')
      return saved ? JSON.parse(saved) : []
    } catch { return [] }
  })

  useEffect(() => {
    localStorage.setItem('nb-wishlist', JSON.stringify(items))
  }, [items])

  const toggle = (product: Product) => {
    setItems(prev =>
      prev.find(i => i.id === product.id)
        ? prev.filter(i => i.id !== product.id)
        : [...prev, product]
    )
  }

  const has = (productId: string) => items.some(i => i.id === productId)

  return (
    <WishlistContext.Provider value={{ items, toggle, has }}>
      {children}
    </WishlistContext.Provider>
  )
}
