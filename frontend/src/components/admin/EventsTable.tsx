import { Event } from '@/api/types';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table';
import { formatDateTime } from '@/lib/utils';

export function EventsTable({ events }: { events: Event[] }) {
  return (
    <Table>
      <TableHead>
        <TableRow>
          <TableHeader>Time</TableHeader>
          <TableHeader>Type</TableHeader>
          <TableHeader>Campaign</TableHeader>
          <TableHeader>Customer</TableHeader>
          <TableHeader>Amount</TableHeader>
        </TableRow>
      </TableHead>
      <TableBody>
        {events.map((e) => (
          <TableRow key={e.id}>
            <TableCell>{formatDateTime(e.occurred_at)}</TableCell>
            <TableCell>{e.type}</TableCell>
            <TableCell>{e.campaign_id}</TableCell>
            <TableCell>{e.customer_id}</TableCell>
            <TableCell>
              {e.amount ? `${e.amount} ${e.currency}` : '-'}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
