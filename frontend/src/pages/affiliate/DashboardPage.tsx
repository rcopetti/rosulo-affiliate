import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getAffiliateDashboard } from '@/api/affiliate/dashboard';
import { getCampaigns } from '@/api/affiliate/campaigns';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { Select } from '@/components/ui/Select';
import { Skeleton } from '@/components/ui/Skeleton';
import { StatsCards } from '@/components/affiliate/StatsCards';
import { LeadVolumeChart } from '@/components/affiliate/LeadVolumeChart';
import { SalesBySequenceChart } from '@/components/affiliate/SalesBySequenceChart';
import { BalanceSummary } from '@/components/affiliate/BalanceSummary';

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

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <h1 className="text-2xl font-bold text-fg">Dashboard</h1>
        <div className="w-full sm:w-64">
          <Select value={campaignId} onChange={setCampaignId} options={campaignOptions} placeholder="Filter by campaign" />
        </div>
      </div>
      <StatsCards
        earned={dashboard.balance.earned}
        pending={dashboard.balance.pending}
        available={dashboard.balance.available}
        paid={dashboard.balance.paid}
        currency={dashboard.balance.currency}
      />
      <BalanceSummary balance={dashboard.balance} />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Lead Volume</CardTitle>
          </CardHeader>
          <LeadVolumeChart data={dashboard.lead_volume} />
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Sales by Sequence</CardTitle>
          </CardHeader>
          <SalesBySequenceChart data={dashboard.sales_by_sequence} currency={dashboard.balance.currency} />
        </Card>
      </div>
    </div>
  );
}
