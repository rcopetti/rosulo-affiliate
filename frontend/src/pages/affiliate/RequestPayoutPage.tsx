import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { getBalance } from '@/api/affiliate/balance';
import { getCommissions } from '@/api/affiliate/commissions';
import { requestPayout } from '@/api/affiliate/payouts';
import { getAffiliateDocuments } from '@/api/affiliate/profile';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { Select } from '@/components/ui/Select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table';
import { useToast } from '@/components/ui/Toast';
import { formatCurrency } from '@/lib/utils';
import { KycStatusBadge } from '@/components/shared/KycStatusBadge';

type PayoutMode = 'all' | 'selected';

export function RequestPayoutPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [currency, setCurrency] = useState('');
  const [mode, setMode] = useState<PayoutMode>('all');
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  const { data: balance, isLoading } = useQuery({ queryKey: ['affiliate-balance'], queryFn: getBalance });
  const { data: commissions } = useQuery({ queryKey: ['affiliate-commissions'], queryFn: () => getCommissions() });
  const { data: documentStatus } = useQuery({
    queryKey: ['affiliate-documents'],
    queryFn: getAffiliateDocuments,
  });

  const eligibility = documentStatus?.payout_eligibility;
  const payoutEligible = eligibility?.eligible ?? false;

  const eligibleCommissions = useMemo(
    () => (commissions ?? []).filter((c) => c.status === 'available' && c.currency === currency),
    [commissions, currency]
  );
  const payable =
    mode === 'selected'
      ? eligibleCommissions.filter((c) => selectedIds.includes(c.id))
      : eligibleCommissions;
  const totals = useMemo(
    () =>
      payable.reduce(
        (acc, c) => ({
          gross: acc.gross + c.gross_amount,
          withholding: acc.withholding + c.withholding_amount,
          net: acc.net + c.net_amount,
        }),
        { gross: 0, withholding: 0, net: 0 }
      ),
    [payable]
  );

  const mutation = useMutation({
    mutationFn: () =>
      requestPayout(
        mode === 'selected'
          ? { currency, commission_ids: payable.map((c) => c.id) }
          : { currency }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['affiliate-balance'] });
      queryClient.invalidateQueries({ queryKey: ['affiliate-commissions'] });
      queryClient.invalidateQueries({ queryKey: ['affiliate-payouts'] });
      toast.add({ title: 'Payout requested', variant: 'success' });
      navigate('/affiliate/payouts');
    },
    onError: () => toast.add({ title: 'Error', description: 'Could not request payout', variant: 'error' }),
  });

  if (isLoading || !balance) return <p className="text-slate-600">Loading…</p>;

  const currencies = new Set<string>();
  balance.balances_by_currency.forEach((item) => {
    if (item.available > 0) currencies.add(item.currency);
  });
  (commissions ?? []).forEach((c) => {
    if (c.status === 'available') currencies.add(c.currency);
  });
  const currencyOptions = [...currencies].sort().map((c) => ({ value: c, label: c }));

  const chooseCurrency = (value: string) => {
    setCurrency(value);
    setSelectedIds([]);
  };

  const toggleCommission = (id: string, checked: boolean) => {
    setSelectedIds((prev) => (checked ? [...prev, id] : prev.filter((x) => x !== id)));
  };

  const allSelected =
    eligibleCommissions.length > 0 && eligibleCommissions.every((c) => selectedIds.includes(c.id));

  const summaryItems = currency
    ? [
        { label: 'Commissions', value: `${payable.length} commission${payable.length === 1 ? '' : 's'}` },
        { label: 'Gross', value: formatCurrency(totals.gross, currency) },
        { label: 'Withholding', value: formatCurrency(totals.withholding, currency) },
        { label: 'Net payout', value: formatCurrency(totals.net, currency) },
      ]
    : [];

  const currencyAvailable =
    balance.balances_by_currency.find((item) => item.currency === currency)?.available ?? 0;
  // In "all" mode the server derives the payable set from the balance, so a
  // currency with available funds is submittable even if the commissions list
  // is empty or still loading. "Selected" mode still requires ≥1 chosen row.
  const hasPayable = mode === 'all' ? currencyAvailable > 0 || payable.length > 0 : payable.length > 0;
  const canSubmit = payoutEligible && Boolean(currency) && hasPayable;
  const submitLabel = !currency
    ? 'Select a currency with available balance'
    : mode === 'all'
      ? hasPayable
        ? `Request payout of ${formatCurrency(currencyAvailable > 0 ? currencyAvailable : totals.net, currency)}`
        : 'No payable commissions in this currency'
      : payable.length > 0
        ? `Request payout of ${formatCurrency(totals.net, currency)}`
        : eligibleCommissions.length > 0 || commissions === undefined
          ? 'Select at least one commission'
          : 'No payable commissions in this currency';

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-2xl font-bold text-slate-900">Request Payout</h1>
      {documentStatus !== undefined && !payoutEligible && (
        <div className="rounded-lg border border-warning/30 bg-warning-soft p-4 text-sm text-warning-fg" role="status">
          {eligibility?.reason || 'Your tax document is not yet eligible for payout.'}
        </div>
      )}
      <Card>
        <CardHeader>
          <CardTitle>Request payout</CardTitle>
        </CardHeader>
        <div className="space-y-4">
          <Select
            label="Payout currency"
            value={currency}
            onChange={chooseCurrency}
            options={currencyOptions}
            placeholder="Choose a currency"
          />
          {currency && (
            <>
              <fieldset className="space-y-2">
                <legend className="text-sm font-medium text-fg">Payout scope</legend>
                <label className="flex items-center gap-2 text-sm text-fg">
                  <input
                    type="radio"
                    name="payout-scope"
                    checked={mode === 'all'}
                    onChange={() => setMode('all')}
                    className="h-4 w-4 accent-primary"
                  />
                  All available
                </label>
                <label className="flex items-center gap-2 text-sm text-fg">
                  <input
                    type="radio"
                    name="payout-scope"
                    checked={mode === 'selected'}
                    onChange={() => setMode('selected')}
                    className="h-4 w-4 accent-primary"
                  />
                  Selected commissions
                </label>
              </fieldset>
              {mode === 'selected' &&
                (commissions === undefined ? (
                  <p className="text-sm text-fg-muted">Loading commissions…</p>
                ) : eligibleCommissions.length === 0 ? (
                  <p className="text-sm text-fg-muted">No available commissions in {currency}.</p>
                ) : (
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableHeader className="w-10">
                          <input
                            type="checkbox"
                            aria-label="Select all commissions"
                            checked={allSelected}
                            onChange={(e) =>
                              setSelectedIds(e.target.checked ? eligibleCommissions.map((c) => c.id) : [])
                            }
                            className="h-4 w-4 accent-primary"
                          />
                        </TableHeader>
                        <TableHeader>Event</TableHeader>
                        <TableHeader className="text-right">Gross</TableHeader>
                        <TableHeader className="text-right">Withholding</TableHeader>
                        <TableHeader className="text-right">Net</TableHeader>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {eligibleCommissions.map((c) => (
                        <TableRow key={c.id}>
                          <TableCell>
                            <input
                              type="checkbox"
                              aria-label={`Select commission ${c.event_id}`}
                              checked={selectedIds.includes(c.id)}
                              onChange={(e) => toggleCommission(c.id, e.target.checked)}
                              className="h-4 w-4 accent-primary"
                            />
                          </TableCell>
                          <TableCell className="truncate font-mono text-xs">{c.event_id}</TableCell>
                          <TableCell className="whitespace-nowrap text-right">
                            {formatCurrency(c.gross_amount, c.currency)}
                          </TableCell>
                          <TableCell className="whitespace-nowrap text-right">
                            {formatCurrency(c.withholding_amount, c.currency)}
                          </TableCell>
                          <TableCell className="whitespace-nowrap text-right font-medium">
                            {formatCurrency(c.net_amount, c.currency)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ))}
              <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {summaryItems.map((item) => (
                  <div key={item.label}>
                    <dt className="text-xs uppercase tracking-wider text-fg-muted">{item.label}</dt>
                    <dd className="mt-1 text-sm font-semibold text-fg">{item.value}</dd>
                  </div>
                ))}
              </dl>
              <p className="text-xs text-fg-muted">
                Preview only — the server confirms the final payout amounts.
              </p>
            </>
          )}
          <p className="flex items-center gap-2 text-sm text-slate-600">
            Tax document status:{' '}
            {documentStatus === undefined ? (
              <span className="text-fg-muted">Loading…</span>
            ) : (
              <KycStatusBadge status={eligibility?.status ?? 'missing'} />
            )}
          </p>
          <Button
            className="w-full"
            onClick={() => mutation.mutate()}
            isLoading={mutation.isPending}
            disabled={!canSubmit}
          >
            {submitLabel}
          </Button>
        </div>
      </Card>
    </div>
  );
}
