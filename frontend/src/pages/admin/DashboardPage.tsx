import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getAdminDashboard } from '@/api/admin/dashboard';
import { approvePayout, rejectPayout } from '@/api/admin/payouts';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { CampaignPerformance } from '@/components/admin/CampaignPerformance';
import { CommissionLiability } from '@/components/admin/CommissionLiability';
import { PayoutQueue } from '@/components/admin/PayoutQueue';
import { KycStatusBadge } from '@/components/shared/KycStatusBadge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table';
import { useToast } from '@/components/ui/Toast';

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

  if (isLoading || !data) return <p className="text-slate-600">Loading…</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Admin Dashboard</h1>
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
          <Table>
            <TableHead>
              <TableRow>
                <TableHeader>Name</TableHeader>
                <TableHeader>Status</TableHeader>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.affiliates.map((a) => (
                <TableRow key={a.id}>
                  <TableCell>{a.name}</TableCell>
                  <TableCell>
                    <KycStatusBadge approved={a.kyc_approved_for_payout} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
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
