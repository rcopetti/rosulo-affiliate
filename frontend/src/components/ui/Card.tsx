import { cn } from '@/lib/utils';
import { ReactNode } from 'react';

interface CardProps {
  children: ReactNode;
  className?: string;
  variant?: 'default' | 'bordered' | 'flat';
}

export function Card({ children, className, variant = 'default' }: CardProps) {
  const variants = {
    default: 'rounded-xl border border-line bg-surface shadow-sm',
    bordered: 'rounded-xl border border-line bg-surface',
    flat: 'rounded-xl bg-surface-muted',
  };
  return <div className={cn(variants[variant], className)}>{children}</div>;
}

interface CardHeaderProps {
  children: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function CardHeader({ children, action, className }: CardHeaderProps) {
  return (
    <div className={cn('mb-4 flex items-center justify-between gap-4 border-b border-line pb-4', className)}>
      <div className="min-w-0">{children}</div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

export function CardTitle({ children, className }: CardProps) {
  return <h3 className={cn('text-lg font-semibold text-fg', className)}>{children}</h3>;
}

export function CardDescription({ children, className }: CardProps) {
  return <p className={cn('mt-1 text-sm text-fg-muted', className)}>{children}</p>;
}

export function CardContent({ children, className }: CardProps) {
  return <div className={cn('', className)}>{children}</div>;
}
