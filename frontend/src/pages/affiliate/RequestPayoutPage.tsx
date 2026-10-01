import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { getBalance } from '@/api/affiliate/balance';
import { requestPayout } from '@/api/affiliate/payouts';
import { getProfile } from '@/api/affiliate/profile';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { Select } from '@/components/ui/Select';
import { useToast } from '@/components/ui/Toast';
import { formatCurrency } from '@/lib/utils';
import { KycStatusBadge } from '@/components/shared/KycStatusBadge';

export function RequestPayoutPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [currency, setCurrency] = useState('');

  const { data: balance, isLoading } = useQuery({ queryKey: ['affiliate-balance'], queryFn: getBalance });
  const { data: profile } = useQuery({ queryKey: ['affiliate-account'], queryFn: getProfile });

  const kycApproved = profile?.documents?.length ? profile.documents.every((d) => d.approved) : false;

  const mutation = useMutation({
    mutationFn: () => requestPayout(currency),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['affiliate-balance'] });
      queryClient.invalidateQueries({ queryKey: ['affiliate-payouts'] });
      toast.add({ title: 'Payout requested', variant: 'success' });
      navigate('/affiliate/payouts');
    },
    onError: () => toast.add({ title: 'Error', description: 'Could not request payout', variant: 'error' }),
  });

  if (isLoading || !balance) return <p className="text-slate-600">Loading…</p>;

  const availableBalances = balance.balances_by_currency.filter((item) => item.available > 0);
  const selectedBalance = availableBalances.find((item) => item.currency === currency);
  const currencyOptions = availableBalances.map((item) => ({
    value: item.currency,
    label: item.currency,
  }));

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-2xl font-bold text-slate-900">Request Payout</h1>
      {!kycApproved && (
        <div className="rounded-lg border border-warning/30 bg-warning-soft p-4 text-sm text-warning-fg" role="status">
          Your documents are not yet approved. You cannot request a payout until KYC is approved.
        </div>
      )}
      <Card>
        <CardHeader>
          <CardTitle>Request amount</CardTitle>
        </CardHeader>
        <div className="space-y-4">
          <Select
            label="Payout currency"
            value={currency}
            onChange={setCurrency}
            options={currencyOptions}
            placeholder="Choose a currency"
          />
          <p className="text-4xl font-bold text-slate-900">
            {selectedBalance
              ? formatCurrency(selectedBalance.available, selectedBalance.currency)
              : 'No available balance'}
          </p>
          <p className="flex items-center gap-2 text-sm text-slate-600">
            KYC status: <KycStatusBadge approved={kycApproved} />
          </p>
          <Button
            className="w-full"
            onClick={() => mutation.mutate()}
            isLoading={mutation.isPending}
            disabled={!kycApproved || !selectedBalance || selectedBalance.available <= 0}
          >
            {selectedBalance
              ? `Request payout of ${formatCurrency(selectedBalance.available, selectedBalance.currency)}`
              : 'Select a currency with available balance'}
          </Button>
        </div>
      </Card>
    </div>
  );
}
