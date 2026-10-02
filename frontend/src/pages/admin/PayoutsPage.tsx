import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getAdminPayouts } from '@/api/admin/payouts';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { PayoutQueue } from '@/components/admin/PayoutQueue';
import { useToast } from '@/components/ui/Toast';
import { approvePayout, confirmPayoutPayment, rejectPayout, retryPayoutNotification } from '@/api/admin/payouts';
import { PayoutPaymentConfirmation } from '@/api/types';

export function AdminPayoutsPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ['admin-payouts'], queryFn: getAdminPayouts });

  const approve = useMutation({
    mutationFn: approvePayout,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-payouts'] });
      queryClient.invalidateQueries({ queryKey: ['admin-dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['admin-payout'] });
      toast.add({ title: 'Payout approved', variant: 'success' });
    },
    onError: () => toast.add({ title: 'Error', description: 'Could not approve', variant: 'error' }),
  });

  const reject = useMutation({
    mutationFn: rejectPayout,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-payouts'] });
      queryClient.invalidateQueries({ queryKey: ['admin-dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['admin-payout'] });
      toast.add({ title: 'Payout rejected', variant: 'success' });
    },
    onError: () => toast.add({ title: 'Error', description: 'Could not reject', variant: 'error' }),
  });

  const confirm = useMutation({
    mutationFn: ({ id, details }: { id: string; details: PayoutPaymentConfirmation }) =>
      confirmPayoutPayment(id, details),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-payouts'] });
      queryClient.invalidateQueries({ queryKey: ['admin-dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['admin-payout'] });
      toast.add({ title: 'Payment recorded', variant: 'success' });
    },
    onError: () => toast.add({ title: 'Error', description: 'Could not record payment', variant: 'error' }),
  });

  const retryNotification = useMutation({
    mutationFn: retryPayoutNotification,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-payouts'] });
      queryClient.invalidateQueries({ queryKey: ['admin-dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['admin-payout'] });
      toast.add({ title: 'Notification email requeued', variant: 'success' });
    },
    onError: () =>
      toast.add({ title: 'Error', description: 'Could not retry notification', variant: 'error' }),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-slate-900">Payouts</h1>
      <Card>
        <CardHeader>
          <CardTitle>Payout requests</CardTitle>
        </CardHeader>
        {isLoading ? (
          <p className="text-sm text-fg-muted">Loading…</p>
        ) : (
          <PayoutQueue
            payouts={data || []}
            onApprove={(id) => approve.mutate(id)}
            onReject={(id) => reject.mutate(id)}
            onConfirmPayment={(id, details) => confirm.mutate({ id, details })}
            onRetryNotification={(id) => retryNotification.mutate(id)}
            isRetryPending={retryNotification.isPending}
          />
        )}
      </Card>
    </div>
  );
}
