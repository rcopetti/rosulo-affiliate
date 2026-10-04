import { useMemo, useState } from 'react';
import { Commission } from '@/api/types';
import { Badge } from '@/components/ui/Badge';
import { DataTable, Column } from '@/components/ui/DataTable';
import { formatCurrency, formatDate } from '@/lib/utils';

const statusVariant: Record<Commission['status'], 'default' | 'success' | 'warning' | 'danger' | 'info'> = {
  pending: 'warning',
  available: 'success',
  reserved: 'info',
  paid: 'info',
  reversed: 'danger',
};

const periodOptions = [
  { value: 'all', label: 'All time' },
  { value: 'today', label: 'Today' },
  { value: 'week', label: 'Last 7 days' },
  { value: 'month', label: 'Last 30 days' },
  { value: 'custom', label: 'Custom' },
] as const;

type Period = (typeof periodOptions)[number]['value'];

const statusOptions = [
  { value: 'all', label: 'All statuses' },
  { value: 'pending', label: 'Pending' },
  { value: 'available', label: 'Available' },
  { value: 'reserved', label: 'Reserved' },
  { value: 'paid', label: 'Paid' },
  { value: 'reversed', label: 'Reversed' },
] as const;

function localDay(isoDate: string, endOfDay = false): Date {
  const [y, m, d] = isoDate.split('-').map(Number);
  return endOfDay
    ? new Date(y, m - 1, d, 23, 59, 59, 999)
    : new Date(y, m - 1, d);
}

function periodStart(period: Period, now: Date): Date | null {
  switch (period) {
    case 'today':
      return new Date(now.getFullYear(), now.getMonth(), now.getDate());
    case 'week':
      return new Date(now.getTime() - 7 * 86_400_000);
    case 'month':
      return new Date(now.getTime() - 30 * 86_400_000);
    default:
      return null;
  }
}

const columns: Column<Commission>[] = [
  {
    key: 'created_at',
    header: 'Date',
    render: (c) => <span className="whitespace-nowrap">{formatDate(c.created_at)}</span>,
    sortValue: (c) => c.created_at,
    className: 'whitespace-nowrap',
    headerClassName: 'w-32',
  },
  {
    key: 'event_id',
    header: 'Event',
    render: (c) => <span className="font-mono text-xs">{c.event_id}</span>,
    className: 'truncate font-mono text-xs',
  },
  {
    key: 'gross_amount',
    header: 'Gross',
    render: (c) => <span className="whitespace-nowrap">{formatCurrency(c.gross_amount, c.currency)}</span>,
    sortValue: (c) => c.gross_amount,
    className: 'text-right whitespace-nowrap',
    headerClassName: 'text-right',
  },
  {
    key: 'withholding_amount',
    header: 'Withholding',
    render: (c) => <span className="whitespace-nowrap">{formatCurrency(c.withholding_amount, c.currency)}</span>,
    sortValue: (c) => c.withholding_amount,
    className: 'text-right whitespace-nowrap',
    headerClassName: 'text-right',
  },
  {
    key: 'net_amount',
    header: 'Net',
    render: (c) => <span className="whitespace-nowrap font-medium">{formatCurrency(c.net_amount, c.currency)}</span>,
    sortValue: (c) => c.net_amount,
    className: 'text-right whitespace-nowrap',
    headerClassName: 'w-32 text-right',
  },
  {
    key: 'status',
    header: 'Status',
    render: (c) => <Badge variant={statusVariant[c.status] || 'default'}>{c.status}</Badge>,
    sortValue: (c) => c.status,
    headerClassName: 'w-28',
  },
];

const selectClass =
  'cursor-pointer rounded-lg border border-line bg-surface px-2 py-1.5 text-sm text-fg focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary';

export function CommissionsTable({ commissions }: { commissions: Commission[] }) {
  const [period, setPeriod] = useState<Period>('all');
  const [status, setStatus] = useState<string>('all');
  const [customFrom, setCustomFrom] = useState('');
  const [customTo, setCustomTo] = useState('');

  const filtered = useMemo(() => {
    const now = new Date();
    let start: Date | null = null;
    let end: Date | null = null;
    if (period === 'custom') {
      start = customFrom ? localDay(customFrom) : null;
      end = customTo ? localDay(customTo, true) : null;
    } else {
      start = periodStart(period, now);
    }
    return commissions.filter((c) => {
      if (status !== 'all' && c.status !== status) return false;
      if (!start && !end) return true;
      if (!c.created_at) return false;
      const created = new Date(c.created_at);
      if (start && created < start) return false;
      if (end && created > end) return false;
      return true;
    });
  }, [commissions, period, status, customFrom, customTo]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-fg-muted">
          Period
          <select
            aria-label="Filter by period"
            value={period}
            onChange={(e) => setPeriod(e.target.value as Period)}
            className={selectClass}
          >
            {periodOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        {period === 'custom' && (
          <>
            <label className="flex items-center gap-2 text-sm text-fg-muted">
              From
              <input
                type="date"
                aria-label="From date"
                value={customFrom}
                onChange={(e) => setCustomFrom(e.target.value)}
                className={selectClass}
              />
            </label>
            <label className="flex items-center gap-2 text-sm text-fg-muted">
              To
              <input
                type="date"
                aria-label="To date"
                value={customTo}
                onChange={(e) => setCustomTo(e.target.value)}
                className={selectClass}
              />
            </label>
          </>
        )}
        <label className="flex items-center gap-2 text-sm text-fg-muted">
          Status
          <select
            aria-label="Filter by status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className={selectClass}
          >
            {statusOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <DataTable
        columns={columns}
        data={filtered}
        rowKey={(c) => c.id}
        emptyTitle={commissions.length === 0 ? 'No commissions yet' : 'No commissions match'}
        emptyDescription={
          commissions.length === 0
            ? 'Commissions appear here once your sales are confirmed.'
            : 'Try a wider period or a different status filter.'
        }
        initialSort={{ key: 'created_at', direction: 'desc' }}
        defaultPageSize={10}
      />
    </div>
  );
}
