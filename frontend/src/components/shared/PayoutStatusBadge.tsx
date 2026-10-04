import { Badge } from '@/components/ui/Badge';
import { PayoutStatus } from '@/api/types';

const VARIANTS: Record<PayoutStatus, 'default' | 'success' | 'warning' | 'danger' | 'info'> = {
  pending_approval: 'warning',
  approved: 'info',
  rejected: 'danger',
  paid: 'success',
};

export function PayoutStatusBadge({ status }: { status: PayoutStatus }) {
  return <Badge variant={VARIANTS[status] ?? 'default'}>{status.replace('_', ' ')}</Badge>;
}
