import * as ToastPrimitive from '@radix-ui/react-toast';
import { CheckCircle2, Info, XCircle } from 'lucide-react';
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

const icons = {
  success: <CheckCircle2 className="h-4 w-4 text-success" aria-hidden="true" />,
  error: <XCircle className="h-4 w-4 text-danger" aria-hidden="true" />,
  info: <Info className="h-4 w-4 text-info" aria-hidden="true" />,
};

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
              'fixed right-4 top-4 z-50 flex items-start gap-2 rounded-lg border px-4 py-3 shadow-lg',
              t.variant === 'success' && 'border-line bg-surface text-fg',
              t.variant === 'error' && 'border-line bg-surface text-fg',
              (!t.variant || t.variant === 'info') && 'border-line bg-surface text-fg'
            )}
          >
            {t.variant && icons[t.variant]}
            <div className="min-w-0">
              {t.title && (
                <ToastPrimitive.Title className="text-sm font-semibold">{t.title}</ToastPrimitive.Title>
              )}
              {t.description && (
                <ToastPrimitive.Description className="text-sm text-fg-muted">
                  {t.description}
                </ToastPrimitive.Description>
              )}
            </div>
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
