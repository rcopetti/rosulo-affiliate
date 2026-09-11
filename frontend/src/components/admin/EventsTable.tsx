import { Event } from '@/api/types';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table';
import { formatDateTime } from '@/lib/utils';

export function EventsTable({ events }: { events: Event[] }) {
  return (
    <Table>
      <TableHead>
        <TableRow>
          <TableHeader>Event ID</TableHeader>
          <TableHeader>Time</TableHeader>
          <TableHeader>Type</TableHeader>
          <TableHeader>Campaign</TableHeader>
          <TableHeader>Affiliate</TableHeader>
          <TableHeader>Customer</TableHeader>
          <TableHeader>Amount</TableHeader>
        </TableRow>
      </TableHead>
      <TableBody>
        {events.map((e) => (
          <TableRow key={e.id}>
            <TableCell className="font-mono text-xs">{e.event_id}</TableCell>
            <TableCell>{formatDateTime(e.occurred_at)}</TableCell>
            <TableCell>{e.type}</TableCell>
            <TableCell className="font-mono text-xs">{e.campaign_id || '-'}</TableCell>
            <TableCell className="font-mono text-xs">{e.affiliate_id || '-'}</TableCell>
            <TableCell>{e.customer_id || '-'}</TableCell>
            <TableCell>
              {e.amount ? `${e.amount} ${e.currency}` : '-'}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
