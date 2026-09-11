import { Balance } from '@/api/types';
import { formatCurrency } from '@/lib/utils';

export function BalanceSummary({ balance }: { balance: Balance }) {
  const items = [
    { label: 'Earned', value: balance.earned },
    { label: 'Pending', value: balance.pending },
    { label: 'Available', value: balance.available },
    { label: 'Paid', value: balance.paid },
    { label: 'Tax retained', value: balance.tax_retained },
    { label: 'Debt', value: balance.debt },
  ];
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((i) => (
        <div key={i.label} className="rounded-lg border border-slate-200 bg-white p-4">
          <p className="text-sm text-slate-500">{i.label}</p>
          <p className="mt-1 text-xl font-semibold text-slate-900">{formatCurrency(i.value, balance.currency)}</p>
        </div>
      ))}
    </div>
  );
}
