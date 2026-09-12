import { DataTable, Column } from '@/components/ui/DataTable';

interface Row {
  campaign_id: string;
  name: string;
  clicks: number;
  leads: number;
  sales: number;
}

const columns: Column<Row>[] = [
  {
    key: 'name',
    header: 'Campaign',
    render: (r) => <span className="font-medium">{r.name}</span>,
    sortValue: (r) => r.name,
    className: 'max-w-0 w-full truncate',
  },
  {
    key: 'clicks',
    header: 'Clicks',
    render: (r) => r.clicks.toLocaleString(),
    sortValue: (r) => r.clicks,
    className: 'text-right tabular-nums',
    headerClassName: 'w-24 text-right',
  },
  {
    key: 'leads',
    header: 'Leads',
    render: (r) => r.leads.toLocaleString(),
    sortValue: (r) => r.leads,
    className: 'text-right tabular-nums',
    headerClassName: 'w-24 text-right',
  },
  {
    key: 'sales',
    header: 'Sales',
    render: (r) => r.sales.toLocaleString(),
    sortValue: (r) => r.sales,
    className: 'text-right tabular-nums',
    headerClassName: 'w-24 text-right',
  },
];

export function CampaignPerformance({ data }: { data: Row[] }) {
  return (
    <DataTable
      columns={columns}
      data={data}
      rowKey={(r) => r.campaign_id}
      emptyTitle="No campaign data yet"
      emptyDescription="Performance metrics appear once campaigns receive traffic."
    />
  );
}
