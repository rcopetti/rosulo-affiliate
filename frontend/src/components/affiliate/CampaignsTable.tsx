import { Campaign } from '@/api/types';
import { Link } from 'react-router-dom';
import { DataTable, Column } from '@/components/ui/DataTable';
import { formatDate } from '@/lib/utils';

const columns: Column<Campaign>[] = [
  {
    key: 'name',
    header: 'Name',
    render: (c) => (
      <Link
        to={`/affiliate/campaigns/${c.id}`}
        className="font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded"
      >
        {c.name}
      </Link>
    ),
    sortValue: (c) => c.name,
    className: 'max-w-0 w-full truncate',
  },
  {
    key: 'tracking_code',
    header: 'Tracking code',
    render: (c) => <span className="font-mono text-xs">{c.tracking_code}</span>,
    headerClassName: 'w-40',
  },
  {
    key: 'landing_url',
    header: 'Landing URL',
    render: (c) => <span className="truncate text-xs">{c.landing_url || '-'}</span>,
    className: 'max-w-0 w-full truncate',
    headerClassName: 'w-56',
  },
  {
    key: 'created_at',
    header: 'Created',
    render: (c) => <span className="whitespace-nowrap text-xs">{formatDate(c.created_at)}</span>,
    sortValue: (c) => new Date(c.created_at).getTime(),
    headerClassName: 'w-32',
  },
];

export function CampaignsTable({ campaigns }: { campaigns: Campaign[] }) {
  return (
    <DataTable
      columns={columns}
      data={campaigns}
      rowKey={(c) => c.id}
      emptyTitle="No campaigns yet"
      emptyDescription="Create your first campaign to start tracking affiliate traffic."
    />
  );
}
