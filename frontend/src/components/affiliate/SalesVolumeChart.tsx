import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { EmptyState } from '@/components/ui/EmptyState';
import { TrendingUp } from 'lucide-react';
import { ChartFallbackTable } from './LeadVolumeChart';

interface DataPoint {
  bucket: string;
  count: number;
}

export function SalesVolumeChart({ data }: { data: DataPoint[] }) {
  if (!data.length) {
    return (
      <EmptyState
        icon={TrendingUp}
        title="No sales data yet"
        description="Sales volume appears here once purchases start coming in."
        className="h-64"
      />
    );
  }

  return (
    <div>
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
            <XAxis dataKey="bucket" tick={{ fontSize: 11, fill: 'rgb(var(--color-fg-muted))' }} stroke="var(--color-border)" />
            <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: 'rgb(var(--color-fg-muted))' }} />
            <Tooltip
              cursor={{ fill: 'rgb(var(--color-surface-muted) / 0.6)' }}
              contentStyle={{
                backgroundColor: 'rgb(var(--color-surface))',
                border: '1px solid rgb(var(--color-border))',
                borderRadius: '0.5rem',
                color: 'rgb(var(--color-fg))',
                fontSize: '0.75rem',
              }}
            />
            <Bar dataKey="count" name="Sales" fill="var(--color-success)" radius={[4, 4, 0, 0]} maxBarSize={48} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ChartFallbackTable
        headers={['Period', 'Sales']}
        rows={data.map((d) => [d.bucket, String(d.count)])}
      />
    </div>
  );
}
