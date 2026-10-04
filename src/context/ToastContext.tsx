import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';

interface Toast {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info';
}

interface ToastContextType {
  showToast: (message: string, type?: 'success' | 'error' | 'info') => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const activeToastKeys = useRef(new Set<string>());
  const dismissTimers = useRef(new Set<ReturnType<typeof setTimeout>>());

  useEffect(() => () => {
    dismissTimers.current.forEach(timer => clearTimeout(timer));
    dismissTimers.current.clear();
    activeToastKeys.current.clear();
  }, []);

  const showToast = useCallback((message: string, type: 'success' | 'error' | 'info' = 'info') => {
    const key = `${type}:${message}`;
    if (activeToastKeys.current.has(key)) return;

    const id = Math.random().toString(36).substring(2, 9);
    activeToastKeys.current.add(key);
    setToasts(prev => [...prev, { id, message, type }]);
    const timer = setTimeout(() => {
      dismissTimers.current.delete(timer);
      activeToastKeys.current.delete(key);
      setToasts(prev => prev.filter(toast => toast.id !== id));
    }, 3000);
    dismissTimers.current.add(timer);
  }, []);

  const value = useMemo(() => ({ showToast }), [showToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 pointer-events-none">
        {toasts.map(toast => (
          <div
            key={toast.id}
            className={`pointer-events-auto px-4 py-3 rounded-lg shadow-lg text-white font-medium text-sm transition-all duration-300 ${
              toast.type === 'success' ? 'bg-emerald-600' :
              toast.type === 'error' ? 'bg-rose-600' : 'bg-neutral-800'
            }`}
          >
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
};

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) throw new Error('useToast must be used within ToastProvider');
  return context;
};
