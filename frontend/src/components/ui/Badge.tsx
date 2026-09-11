import { cn } from '@/lib/utils';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info';
  className?: string;
}

export function Badge({ children, variant = 'default', className }: BadgeProps) {
  const variants = {
    default: 'bg-surface-muted text-fg-muted border border-line',
    success: 'bg-success-soft text-success-fg',
    warning: 'bg-warning-soft text-warning-fg',
    danger: 'bg-danger-soft text-danger-fg',
    info: 'bg-info-soft text-info-fg',
  };
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap',
        variants[variant],
        className
      )}
    >
      {children}
    </span>
  );
}
