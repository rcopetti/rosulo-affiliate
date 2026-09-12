import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ChartFallbackTable } from './LeadVolumeChart';
import { formatCurrency } from '@/lib/utils';

interface DataPoint {
  sequence: number;
  count: number;
  amount: number;
}

export function SalesBySequenceChart({ data, currency = 'USD' }: { data: DataPoint[]; currency?: string }) {
  if (!data.length) {
    return (
      <div className="flex h-64 items-center justify-center text-sm text-fg-muted">
        No sales recorded yet
      </div>
    );
  }

  return (
    <div>
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
            <XAxis dataKey="sequence" tick={{ fontSize: 11, fill: 'rgb(var(--color-fg-muted))' }} />
            <YAxis tick={{ fontSize: 11, fill: 'rgb(var(--color-fg-muted))' }} />
            <Tooltip
              formatter={(value: number | string) => formatCurrency(Number(value), currency)}
              contentStyle={{
                backgroundColor: 'rgb(var(--color-surface))',
                border: '1px solid rgb(var(--color-border))',
                borderRadius: '0.5rem',
                fontSize: '0.75rem',
                color: 'rgb(var(--color-fg))',
              }}
            />
            <Bar dataKey="amount" name="Sales" fill="var(--color-success)" radius={[4, 4, 0, 0]} maxBarSize={48} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ChartFallbackTable
        headers={['Payment sequence', 'Amount']}
        rows={data.map((d) => [`#${d.sequence}`, formatCurrency(d.amount, currency)])}
      />
    </div>
  );
}
