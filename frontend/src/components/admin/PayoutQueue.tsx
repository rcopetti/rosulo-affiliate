import { Payout } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table';
import { PayoutStatusBadge } from '@/components/shared/PayoutStatusBadge';
import { formatCurrency } from '@/lib/utils';

interface PayoutQueueProps {
  payouts: Payout[];
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
}

export function PayoutQueue({ payouts, onApprove, onReject }: PayoutQueueProps) {
  return (
    <Table>
      <TableHead>
        <TableRow>
          <TableHeader>Requested</TableHeader>
          <TableHeader>Amount</TableHeader>
          <TableHeader>Status</TableHeader>
          <TableHeader>Actions</TableHeader>
        </TableRow>
      </TableHead>
      <TableBody>
        {payouts.map((p) => (
          <TableRow key={p.id}>
            <TableCell>{new Date(p.requested_at).toLocaleString()}</TableCell>
            <TableCell>{formatCurrency(p.requested_amount, p.currency)}</TableCell>
            <TableCell>
              <PayoutStatusBadge status={p.status} />
            </TableCell>
            <TableCell>
              <div className="flex gap-2">
                <Button size="sm" onClick={() => onApprove(p.id)}>
                  Approve
                </Button>
                <Button variant="danger" size="sm" onClick={() => onReject(p.id)}>
                  Reject
                </Button>
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
