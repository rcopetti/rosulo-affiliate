import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { EmptyState } from '@/components/ui/EmptyState';
import { TrendingUp } from 'lucide-react';

interface DataPoint {
  bucket: string;
  count: number;
}

export function LeadVolumeChart({ data }: { data: DataPoint[] }) {
  if (!data.length) {
    return (
      <EmptyState
        icon={TrendingUp}
        title="No lead data yet"
        description="Lead volume appears here once registrations start coming in."
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
            <Bar dataKey="count" name="Leads" fill="var(--color-primary)" radius={[4, 4, 0, 0]} maxBarSize={48} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ChartFallbackTable
        headers={['Period', 'Leads']}
        rows={data.map((d) => [d.bucket, String(d.count)])}
      />
    </div>
  );
}

export function ChartFallbackTable({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return (
    <details className="mt-2 text-xs text-fg-muted">
      <summary className="cursor-pointer select-none hover:text-fg">View data as table</summary>
      <table className="mt-2 w-full text-left text-xs">
        <thead>
          <tr>
            {headers.map((h) => (
              <th key={h} scope="col" className="px-2 py-1 font-semibold text-fg-muted">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-t border-line">
              {row.map((cell, j) => (
                <td key={j} className="px-2 py-1 tabular-nums">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}
