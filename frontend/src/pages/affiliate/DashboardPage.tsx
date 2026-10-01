import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getAffiliateDashboard } from '@/api/affiliate/dashboard';
import { getCampaigns } from '@/api/affiliate/campaigns';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { Select } from '@/components/ui/Select';
import { Skeleton } from '@/components/ui/Skeleton';
import { LeadVolumeChart } from '@/components/affiliate/LeadVolumeChart';
import { SalesBySequenceChart } from '@/components/affiliate/SalesBySequenceChart';
import { CurrencyBalances } from '@/components/affiliate/CurrencyBalances';

export function DashboardPage() {
  const [campaignId, setCampaignId] = useState<string>('');
  const { data: dashboard, isLoading } = useQuery({
    queryKey: ['affiliate-dashboard', campaignId || null],
    queryFn: () => getAffiliateDashboard(campaignId || undefined),
  });
  const { data: campaigns } = useQuery({ queryKey: ['affiliate-campaigns'], queryFn: getCampaigns });

  if (isLoading || !dashboard)
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-72" />
          <Skeleton className="h-72" />
        </div>
      </div>
    );

  const campaignOptions = [{ value: '', label: 'All campaigns' }, ...(campaigns || []).map((c) => ({ value: c.id, label: c.name }))];
  const salesCurrencies = dashboard.sales_by_sequence.length
    ? [...new Set(dashboard.sales_by_sequence.map((row) => row.currency))]
    : ['USD'];

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <h1 className="text-2xl font-bold text-fg">Dashboard</h1>
        <div className="w-full sm:w-64">
          <Select value={campaignId} onChange={setCampaignId} options={campaignOptions} placeholder="Filter by campaign" />
        </div>
      </div>
      <CurrencyBalances balance={dashboard.balance} />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Lead Volume</CardTitle>
          </CardHeader>
          <LeadVolumeChart data={dashboard.lead_volume} />
        </Card>
        {salesCurrencies.map((currency) => (
          <Card key={currency}>
            <CardHeader>
              <CardTitle>Sales by Sequence — {currency}</CardTitle>
            </CardHeader>
            <SalesBySequenceChart
              data={dashboard.sales_by_sequence.filter((row) => row.currency === currency)}
              currency={currency}
            />
          </Card>
        ))}
      </div>
    </div>
  );
}
