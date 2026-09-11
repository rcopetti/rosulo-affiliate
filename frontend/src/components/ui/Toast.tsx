import * as ToastPrimitive from '@radix-ui/react-toast';
import { createContext, ReactNode, useCallback, useContext, useState } from 'react';
import { cn } from '@/lib/utils';

interface Toast {
  id: string;
  title?: string;
  description?: string;
  variant?: 'success' | 'error' | 'info';
}

interface ToastContextValue {
  add: (toast: Omit<Toast, 'id'>) => void;
  remove: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const add = useCallback((toast: Omit<Toast, 'id'>) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((prev) => [...prev, { ...toast, id }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 5000);
  }, []);

  const remove = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ add, remove }}>
      <ToastPrimitive.Provider>
        {children}
        {toasts.map((t) => (
          <ToastPrimitive.Root
            key={t.id}
            open
            onOpenChange={() => remove(t.id)}
            className={cn(
              'fixed right-4 top-4 z-50 rounded-lg px-4 py-3 shadow-lg border',
              t.variant === 'success' && 'bg-green-50 border-green-200 text-green-900',
              t.variant === 'error' && 'bg-red-50 border-red-200 text-red-900',
              (!t.variant || t.variant === 'info') && 'bg-white border-slate-200 text-slate-900'
            )}
          >
            {t.title && <ToastPrimitive.Title className="font-semibold text-sm">{t.title}</ToastPrimitive.Title>}
            {t.description && <ToastPrimitive.Description className="text-sm">{t.description}</ToastPrimitive.Description>}
          </ToastPrimitive.Root>
        ))}
        <ToastPrimitive.Viewport className="fixed right-0 top-0 z-50 p-4" />
      </ToastPrimitive.Provider>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}
