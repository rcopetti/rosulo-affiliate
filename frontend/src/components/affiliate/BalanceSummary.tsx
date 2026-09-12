import { Card } from '@/components/ui/Card';
import { Balance } from '@/api/types';
import { formatCurrency } from '@/lib/utils';

/**
 * Secondary balance metrics. The primary KPIs (earned, pending, available, paid)
 * are shown in StatsCards; this section only covers the remaining figures.
 */
export function BalanceSummary({ balance }: { balance: Balance }) {
  const items = [
    { label: 'Tax retained', value: balance.tax_retained },
    { label: 'Debt', value: balance.debt },
  ];
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {items.map((i) => (
        <Card key={i.label} className="p-5">
          <p className="text-sm text-fg-muted">{i.label}</p>
          <p className="mt-1 truncate text-2xl font-bold tracking-tight text-fg">
            {formatCurrency(i.value, balance.currency)}
          </p>
        </Card>
      ))}
    </div>
  );
}
