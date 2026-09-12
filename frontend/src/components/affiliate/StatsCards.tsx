import { Card } from '@/components/ui/Card';
import { CircleDollarSign, Clock, Wallet, HandCoins } from 'lucide-react';
import { formatCurrency } from '@/lib/utils';
import { cn } from '@/lib/utils';
import { LucideIcon } from 'lucide-react';

interface StatsCardsProps {
  earned: number;
  pending: number;
  available: number;
  paid: number;
  currency: string;
}

interface StatItem {
  label: string;
  value: number;
  icon: LucideIcon;
  accent: string;
}

export function StatsCards({ earned, pending, available, paid, currency }: StatsCardsProps) {
  const items: StatItem[] = [
    { label: 'Earned', value: earned, icon: CircleDollarSign, accent: 'text-info bg-info-soft' },
    { label: 'Pending', value: pending, icon: Clock, accent: 'text-warning bg-warning-soft' },
    { label: 'Available', value: available, icon: Wallet, accent: 'text-success bg-success-soft' },
    { label: 'Paid', value: paid, icon: HandCoins, accent: 'text-fg-muted bg-surface-muted' },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {items.map((i) => (
        <Card key={i.label} className="p-5">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm text-fg-muted">{i.label}</p>
              <p className="mt-1 truncate text-2xl font-bold tracking-tight text-fg">
                {formatCurrency(i.value, currency)}
              </p>
            </div>
            <span className={cn('flex h-9 w-9 shrink-0 items-center justify-center rounded-full', i.accent)}>
              <i.icon className="h-5 w-5" aria-hidden="true" />
            </span>
          </div>
        </Card>
      ))}
    </div>
  );
}
