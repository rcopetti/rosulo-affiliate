import { Commission } from '@/api/types';
import { Badge } from '@/components/ui/Badge';
import { DataTable, Column } from '@/components/ui/DataTable';
import { formatCurrency } from '@/lib/utils';

const statusVariant: Record<string, 'default' | 'success' | 'warning' | 'danger' | 'info'> = {
  pending: 'warning',
  available: 'success',
  paid: 'info',
  reversed: 'danger',
};

const columns: Column<Commission>[] = [
  {
    key: 'event_id',
    header: 'Event',
    render: (c) => <span className="font-mono text-xs">{c.event_id}</span>,
    className: 'truncate font-mono text-xs max-w-0 w-full',
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

export function CommissionsTable({ commissions }: { commissions: Commission[] }) {
  return (
    <DataTable
      columns={columns}
      data={commissions}
      rowKey={(c) => c.id}
      emptyTitle="No commissions yet"
      emptyDescription="Commissions appear here once your sales are confirmed."
    />
  );
}
