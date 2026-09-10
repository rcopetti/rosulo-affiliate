import { Commission } from '@/api/types';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table';
import { formatCurrency } from '@/lib/utils';

export function CommissionsTable({ commissions }: { commissions: Commission[] }) {
  return (
    <Table>
      <TableHead>
        <TableRow>
          <TableHeader>Event</TableHeader>
          <TableHeader>Gross</TableHeader>
          <TableHeader>Withholding</TableHeader>
          <TableHeader>Net</TableHeader>
          <TableHeader>Status</TableHeader>
        </TableRow>
      </TableHead>
      <TableBody>
        {commissions.map((c) => (
          <TableRow key={c.id}>
            <TableCell>{c.event_id}</TableCell>
            <TableCell>{formatCurrency(c.gross_amount, c.currency)}</TableCell>
            <TableCell>{formatCurrency(c.withholding_amount, c.currency)}</TableCell>
            <TableCell>{formatCurrency(c.net_amount, c.currency)}</TableCell>
            <TableCell>{c.status}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
