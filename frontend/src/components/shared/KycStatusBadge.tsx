import { Badge } from '@/components/ui/Badge';

export function KycStatusBadge({ approved }: { approved: boolean }) {
  return approved ? <Badge variant="success">KYC Approved</Badge> : <Badge variant="warning">KYC Pending</Badge>;
}
