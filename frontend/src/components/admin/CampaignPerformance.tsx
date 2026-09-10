import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table';

interface Row {
  campaign_id: string;
  name: string;
  clicks: number;
  leads: number;
  sales: number;
}

export function CampaignPerformance({ data }: { data: Row[] }) {
  return (
    <Table>
      <TableHead>
        <TableRow>
          <TableHeader>Campaign</TableHeader>
          <TableHeader>Clicks</TableHeader>
          <TableHeader>Leads</TableHeader>
          <TableHeader>Sales</TableHeader>
        </TableRow>
      </TableHead>
      <TableBody>
        {data.map((r) => (
          <TableRow key={r.campaign_id}>
            <TableCell>{r.name}</TableCell>
            <TableCell>{r.clicks}</TableCell>
            <TableCell>{r.leads}</TableCell>
            <TableCell>{r.sales}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
