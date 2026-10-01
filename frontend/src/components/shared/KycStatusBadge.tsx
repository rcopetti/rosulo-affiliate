import { Badge } from '@/components/ui/Badge';
import { PayoutEligibilityStatus } from '@/api/types';

const statusDisplay: Record<PayoutEligibilityStatus, { label: string; variant: 'success' | 'warning' | 'danger' }> = {
  missing: { label: 'Tax form missing', variant: 'warning' },
  pending: { label: 'Tax form pending', variant: 'warning' },
  approved: { label: 'Tax form approved', variant: 'success' },
  rejected: { label: 'Tax form rejected', variant: 'danger' },
};

export function KycStatusBadge({ status }: { status: PayoutEligibilityStatus }) {
  const display = statusDisplay[status];
  return <Badge variant={display.variant}>{display.label}</Badge>;
}
