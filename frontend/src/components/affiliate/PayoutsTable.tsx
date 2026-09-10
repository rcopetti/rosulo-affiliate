import { Payout } from '@/api/types';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table';
import { PayoutStatusBadge } from '@/components/shared/PayoutStatusBadge';
import { formatCurrency, formatDateTime } from '@/lib/utils';

export function PayoutsTable({ payouts }: { payouts: Payout[] }) {
  return (
    <Table>
      <TableHead>
        <TableRow>
          <TableHeader>Requested</TableHeader>
          <TableHeader>Gross</TableHeader>
          <TableHeader>Withholding</TableHeader>
          <TableHeader>Net</TableHeader>
          <TableHeader>Status</TableHeader>
        </TableRow>
      </TableHead>
      <TableBody>
        {payouts.map((p) => (
          <TableRow key={p.id}>
            <TableCell>{formatDateTime(p.requested_at)}</TableCell>
            <TableCell>{formatCurrency(p.requested_amount, p.currency)}</TableCell>
            <TableCell>{formatCurrency(p.withholding_total, p.currency)}</TableCell>
            <TableCell>{formatCurrency(p.net_paid, p.currency)}</TableCell>
            <TableCell>
              <PayoutStatusBadge status={p.status} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
