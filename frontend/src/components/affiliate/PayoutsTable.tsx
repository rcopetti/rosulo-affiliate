import { Payout } from '@/api/types';
import { DataTable, Column } from '@/components/ui/DataTable';
import { PayoutStatusBadge } from '@/components/shared/PayoutStatusBadge';
import { formatCurrency, formatDateTime } from '@/lib/utils';

const columns: Column<Payout>[] = [
  {
    key: 'requested_at',
    header: 'Requested',
    render: (p) => <span className="whitespace-nowrap text-xs">{formatDateTime(p.requested_at)}</span>,
    sortValue: (p) => new Date(p.requested_at).getTime(),
    headerClassName: 'w-44',
  },
  {
    key: 'requested_amount',
    header: 'Gross',
    render: (p) => <span className="whitespace-nowrap">{formatCurrency(p.requested_amount, p.currency)}</span>,
    sortValue: (p) => p.requested_amount,
    className: 'text-right whitespace-nowrap',
    headerClassName: 'text-right',
  },
  {
    key: 'withholding_total',
    header: 'Withholding',
    render: (p) => <span className="whitespace-nowrap">{formatCurrency(p.withholding_total, p.currency)}</span>,
    className: 'text-right whitespace-nowrap',
    headerClassName: 'text-right',
  },
  {
    key: 'net_paid',
    header: 'Net',
    render: (p) => <span className="whitespace-nowrap font-medium">{formatCurrency(p.net_paid, p.currency)}</span>,
    sortValue: (p) => p.net_paid,
    className: 'text-right whitespace-nowrap',
    headerClassName: 'w-32 text-right',
  },
  {
    key: 'status',
    header: 'Status',
    render: (p) => <PayoutStatusBadge status={p.status} />,
    headerClassName: 'w-36',
  },
];

export function PayoutsTable({ payouts }: { payouts: Payout[] }) {
  return (
    <DataTable
      columns={columns}
      data={payouts}
      rowKey={(p) => p.id}
      emptyTitle="No payouts yet"
      emptyDescription="Request a payout from your balance to see it here."
    />
  );
}
