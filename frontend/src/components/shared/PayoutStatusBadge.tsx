import { Badge } from '@/components/ui/Badge';
import { Payout } from '@/api/types';

export function PayoutStatusBadge({ status }: { status: Payout['status'] }) {
  const variant: Record<string, 'default' | 'success' | 'warning' | 'danger' | 'info'> = {
    requested: 'default',
    pending_approval: 'warning',
    approved: 'info',
    processing: 'info',
    paid: 'success',
    failed: 'danger',
    rejected: 'danger',
  };
  return <Badge variant={variant[status] || 'default'}>{status.replace('_', ' ')}</Badge>;
}
