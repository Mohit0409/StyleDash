import React, { createContext, useContext, useState, useEffect } from 'react'
import type { CartItem, Product } from '../types'

interface CartContextType {
  items: CartItem[]
  addItem: (product: Product) => void
  removeItem: (productId: string) => void
  updateQty: (productId: string, qty: number) => void
  clearCart: () => void
  total: number
  itemCount: number
  isOpen: boolean
  setIsOpen: (open: boolean) => void
}

const CartContext = createContext<CartContextType | null>(null)

export const useCart = () => {
  const ctx = useContext(CartContext)
  if (!ctx) throw new Error('useCart must be used within CartProvider')
  return ctx
}

export const CartProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [items, setItems] = useState<CartItem[]>(() => {
    try {
      const saved = localStorage.getItem('nb-cart')
      return saved ? JSON.parse(saved) : []
    } catch { return [] }
  })
  const [isOpen, setIsOpen] = useState(false)

  useEffect(() => {
    localStorage.setItem('nb-cart', JSON.stringify(items))
  }, [items])

  const addItem = (product: Product) => {
    setItems(prev => {
      const existing = prev.find(i => i.product.id === product.id)
      if (existing) {
        return prev.map(i => i.product.id === product.id ? { ...i, quantity: i.quantity + 1 } : i)
      }
      return [...prev, { product, quantity: 1 }]
    })
  }

  const removeItem = (productId: string) => {
    setItems(prev => prev.filter(i => i.product.id !== productId))
  }

  const updateQty = (productId: string, qty: number) => {
    if (qty <= 0) { removeItem(productId); return }
    setItems(prev => prev.map(i => i.product.id === productId ? { ...i, quantity: qty } : i))
  }

  const clearCart = () => setItems([])

  const total = items.reduce((sum, i) => sum + i.product.price * i.quantity, 0)
  const itemCount = items.reduce((sum, i) => sum + i.quantity, 0)

  return (
    <CartContext.Provider value={{ items, addItem, removeItem, updateQty, clearCart, total, itemCount, isOpen, setIsOpen }}>
      {children}
    </CartContext.Provider>
  )
}
