import { Card } from '@/components/ui/Card';
import { formatCurrency } from '@/lib/utils';

interface StatsCardsProps {
  earned: number;
  pending: number;
  available: number;
  paid: number;
  currency: string;
}

export function StatsCards({ earned, pending, available, paid, currency }: StatsCardsProps) {
  const items = [
    { label: 'Earned', value: earned },
    { label: 'Pending', value: pending },
    { label: 'Available', value: available },
    { label: 'Paid', value: paid },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {items.map((i) => (
        <Card key={i.label}>
          <p className="text-sm text-slate-500">{i.label}</p>
          <p className="mt-1 text-2xl font-bold text-slate-900">{formatCurrency(i.value, currency)}</p>
        </Card>
      ))}
    </div>
  );
}
