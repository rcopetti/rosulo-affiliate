import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getAdminDashboard } from '@/api/admin/dashboard';
import { approvePayout, rejectPayout } from '@/api/admin/payouts';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { DataTable, Column } from '@/components/ui/DataTable';
import { Skeleton } from '@/components/ui/Skeleton';
import { CampaignPerformance } from '@/components/admin/CampaignPerformance';
import { CommissionLiability } from '@/components/admin/CommissionLiability';
import { PayoutQueue } from '@/components/admin/PayoutQueue';
import { KycStatusBadge } from '@/components/shared/KycStatusBadge';
import { useToast } from '@/components/ui/Toast';

const affiliateColumns: Column<{ id: string; name: string; kyc_approved_for_payout: boolean }>[] = [
  {
    key: 'name',
    header: 'Name',
    render: (a) => <span className="font-medium">{a.name}</span>,
    sortValue: (a) => a.name,
    className: 'max-w-0 w-full truncate',
  },
  {
    key: 'kyc',
    header: 'Status',
    render: (a) => <KycStatusBadge approved={a.kyc_approved_for_payout} />,
    headerClassName: 'w-36',
  },
];

export function AdminDashboardPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ['admin-dashboard'], queryFn: getAdminDashboard });

  const approve = useMutation({
    mutationFn: approvePayout,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-dashboard'] });
      toast.add({ title: 'Payout approved', variant: 'success' });
    },
    onError: () => toast.add({ title: 'Error', description: 'Could not approve payout', variant: 'error' }),
  });

  const reject = useMutation({
    mutationFn: rejectPayout,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-dashboard'] });
      toast.add({ title: 'Payout rejected', variant: 'success' });
    },
    onError: () => toast.add({ title: 'Error', description: 'Could not reject payout', variant: 'error' }),
  });

  if (isLoading || !data)
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-56" />
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
      </div>
    );

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-fg">Admin Dashboard</h1>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Campaign performance</CardTitle>
          </CardHeader>
          <CampaignPerformance data={data.campaign_performance} />
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Affiliates</CardTitle>
          </CardHeader>
          <DataTable
            columns={affiliateColumns}
            data={data.affiliates}
            rowKey={(a) => a.id}
            emptyTitle="No affiliates yet"
            emptyDescription="Invite affiliates to start building your program."
          />
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Commission liability</CardTitle>
          </CardHeader>
          <CommissionLiability data={data.commission_liability} />
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Payout queue</CardTitle>
          </CardHeader>
          <PayoutQueue
            payouts={data.payout_queue}
            onApprove={(id) => approve.mutate(id)}
            onReject={(id) => reject.mutate(id)}
          />
        </Card>
      </div>
    </div>
  );
}
