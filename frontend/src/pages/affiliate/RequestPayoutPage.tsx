import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { getBalance } from '@/api/affiliate/balance';
import { requestPayout } from '@/api/affiliate/payouts';
import { getProfile } from '@/api/affiliate/profile';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { useToast } from '@/components/ui/Toast';
import { formatCurrency } from '@/lib/utils';
import { KycStatusBadge } from '@/components/shared/KycStatusBadge';

export function RequestPayoutPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();

  const { data: balance, isLoading } = useQuery({ queryKey: ['affiliate-balance'], queryFn: getBalance });
  const { data: profile } = useQuery({ queryKey: ['affiliate-account'], queryFn: getProfile });

  const kycApproved = profile?.documents.every((d) => d.status === 'approved') ?? false;

  const mutation = useMutation({
    mutationFn: () => requestPayout(balance?.available || 0),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['affiliate-balance'] });
      queryClient.invalidateQueries({ queryKey: ['affiliate-payouts'] });
      toast.add({ title: 'Payout requested', variant: 'success' });
      navigate('/affiliate/payouts');
    },
    onError: () => toast.add({ title: 'Error', description: 'Could not request payout', variant: 'error' }),
  });

  if (isLoading || !balance) return <p className="text-slate-600">Loading…</p>;

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-2xl font-bold text-slate-900">Request Payout</h1>
      {!kycApproved && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          Your documents are not yet approved. You cannot request a payout until KYC is approved.
        </div>
      )}
      <Card>
        <CardHeader>
          <CardTitle>Available balance</CardTitle>
        </CardHeader>
        <div className="px-6 pb-6">
          <p className="text-4xl font-bold text-slate-900">{formatCurrency(balance.available, balance.currency)}</p>
          <p className="mt-2 flex items-center gap-2 text-sm text-slate-600">
            KYC status: <KycStatusBadge approved={kycApproved} />
          </p>
          <Button
            className="mt-4 w-full"
            onClick={() => mutation.mutate()}
            isLoading={mutation.isPending}
            disabled={!kycApproved || balance.available <= 0}
          >
            Request payout of {formatCurrency(balance.available, balance.currency)}
          </Button>
        </div>
      </Card>
    </div>
  );
}
