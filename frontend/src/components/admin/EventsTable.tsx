import { Event } from '@/api/types';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table';
import { formatCurrency, formatDateTime } from '@/lib/utils';

export function EventsTable({ events }: { events: Event[] }) {
  return (
    <Table className="w-full table-fixed">
      <TableHead>
        <TableRow>
          <TableHeader className="w-40">Event ID</TableHeader>
          <TableHeader className="w-48">Time</TableHeader>
          <TableHeader className="w-16">Type</TableHeader>
          <TableHeader className="w-40">Campaign</TableHeader>
          <TableHeader className="w-40">Affiliate</TableHeader>
          <TableHeader className="w-40">Customer</TableHeader>
          <TableHeader className="w-24 text-right">Amount</TableHeader>
        </TableRow>
      </TableHead>
      <TableBody>
        {events.map((e) => (
          <TableRow key={e.id}>
            <TableCell className="truncate font-mono text-xs">{e.event_id}</TableCell>
            <TableCell className="whitespace-nowrap overflow-hidden text-xs">{formatDateTime(e.occurred_at)}</TableCell>
            <TableCell className="whitespace-nowrap text-xs capitalize">{e.type}</TableCell>
            <TableCell className="truncate font-mono text-xs">{e.campaign_id || '-'}</TableCell>
            <TableCell className="truncate font-mono text-xs">{e.affiliate_id || '-'}</TableCell>
            <TableCell className="truncate text-xs">{e.customer_id || '-'}</TableCell>
            <TableCell className="whitespace-nowrap text-right text-xs">
              {e.amount ? formatCurrency(e.amount, e.currency || 'USD') : '-'}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
