import { Event } from '@/api/types';
import { DataTable, Column } from '@/components/ui/DataTable';
import { formatCurrency, formatDateTime } from '@/lib/utils';

const columns: Column<Event>[] = [
  {
    key: 'event_id',
    header: 'Event ID',
    render: (e) => <span className="font-mono text-xs">{e.event_id}</span>,
    className: 'truncate font-mono text-xs',
    headerClassName: 'w-40',
  },
  {
    key: 'occurred_at',
    header: 'Time',
    render: (e) => <span className="whitespace-nowrap text-xs">{formatDateTime(e.occurred_at)}</span>,
    sortValue: (e) => new Date(e.occurred_at).getTime(),
    className: 'overflow-hidden',
    headerClassName: 'w-44',
  },
  {
    key: 'type',
    header: 'Type',
    render: (e) => <span className="whitespace-nowrap text-xs capitalize">{e.type}</span>,
    sortValue: (e) => e.type,
    headerClassName: 'w-20',
  },
  {
    key: 'campaign_id',
    header: 'Campaign',
    render: (e) => <span className="font-mono text-xs">{e.campaign_id || '-'}</span>,
    className: 'truncate font-mono text-xs',
    headerClassName: 'w-36',
  },
  {
    key: 'affiliate_id',
    header: 'Affiliate',
    render: (e) => <span className="font-mono text-xs">{e.affiliate_id || '-'}</span>,
    className: 'truncate font-mono text-xs',
    headerClassName: 'w-36',
  },
  {
    key: 'customer_id',
    header: 'Customer',
    render: (e) => <span className="text-xs">{e.customer_id || '-'}</span>,
    className: 'truncate',
    headerClassName: 'w-32',
  },
  {
    key: 'amount',
    header: 'Amount',
    render: (e) => (
      <span className="whitespace-nowrap text-xs">
        {e.amount ? formatCurrency(e.amount, e.currency || 'USD') : '-'}
      </span>
    ),
    sortValue: (e) => e.amount || 0,
    headerClassName: 'w-28 text-right',
    className: 'overflow-hidden text-right',
  },
];

export function EventsTable({ events }: { events: Event[] }) {
  return <DataTable columns={columns} data={events} rowKey={(e) => e.id} emptyTitle="No events yet" />;
}
