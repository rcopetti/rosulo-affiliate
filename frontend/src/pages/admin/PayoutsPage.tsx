import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getAdminPayouts } from '@/api/admin/payouts';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { PayoutQueue } from '@/components/admin/PayoutQueue';
import { useToast } from '@/components/ui/Toast';
import { approvePayout, rejectPayout } from '@/api/admin/payouts';

export function AdminPayoutsPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ['admin-payouts'], queryFn: getAdminPayouts });

  const approve = useMutation({
    mutationFn: approvePayout,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-payouts'] });
      toast.add({ title: 'Payout approved', variant: 'success' });
    },
    onError: () => toast.add({ title: 'Error', description: 'Could not approve', variant: 'error' }),
  });

  const reject = useMutation({
    mutationFn: rejectPayout,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-payouts'] });
      toast.add({ title: 'Payout rejected', variant: 'success' });
    },
    onError: () => toast.add({ title: 'Error', description: 'Could not reject', variant: 'error' }),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-slate-900">Payouts</h1>
      <Card>
        <CardHeader>
          <CardTitle>Payout requests</CardTitle>
        </CardHeader>
        {isLoading ? (
          <p className="p-4 text-slate-600">Loading…</p>
        ) : (
          <PayoutQueue
            payouts={data || []}
            onApprove={(id) => approve.mutate(id)}
            onReject={(id) => reject.mutate(id)}
          />
        )}
      </Card>
    </div>
  );
}
