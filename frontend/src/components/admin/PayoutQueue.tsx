import { Payout } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { DataTable, Column } from '@/components/ui/DataTable';
import { PayoutStatusBadge } from '@/components/shared/PayoutStatusBadge';
import { formatCurrency, formatDateTime } from '@/lib/utils';

interface PayoutQueueProps {
  payouts: Payout[];
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
}

export function PayoutQueue({ payouts, onApprove, onReject }: PayoutQueueProps) {
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
      header: 'Amount',
      render: (p) => <span className="whitespace-nowrap">{formatCurrency(p.requested_amount, p.currency)}</span>,
      sortValue: (p) => p.requested_amount,
      className: 'text-right whitespace-nowrap',
      headerClassName: 'w-32 text-right',
    },
    {
      key: 'status',
      header: 'Status',
      render: (p) => <PayoutStatusBadge status={p.status} />,
      headerClassName: 'w-36',
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (p) => (
        <div className="flex gap-2">
          <Button size="sm" onClick={() => onApprove(p.id)}>
            Approve
          </Button>
          <Button variant="danger" size="sm" onClick={() => onReject(p.id)}>
            Reject
          </Button>
        </div>
      ),
      headerClassName: 'w-44',
    },
  ];

  return (
    <DataTable
      columns={columns}
      data={payouts}
      rowKey={(p) => p.id}
      emptyTitle="Payout queue is empty"
      emptyDescription="Payout requests from affiliates will appear here for approval."
    />
  );
}
