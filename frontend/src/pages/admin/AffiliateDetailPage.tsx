import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams, Link } from 'react-router-dom';
import { approveKyc, getAffiliate, rejectKyc } from '@/api/admin/affiliates';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { KycStatusBadge } from '@/components/shared/KycStatusBadge';
import { useToast } from '@/components/ui/Toast';

export function AffiliateDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const toast = useToast();
  const { data, isLoading } = useQuery({
    queryKey: ['admin-affiliate', id],
    queryFn: () => getAffiliate(id!),
    enabled: !!id,
  });

  const approve = useMutation({
    mutationFn: () => approveKyc(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-affiliate', id] });
      toast.add({ title: 'KYC approved', variant: 'success' });
    },
    onError: () => toast.add({ title: 'Error', description: 'Could not approve KYC', variant: 'error' }),
  });

  const reject = useMutation({
    mutationFn: () => rejectKyc(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-affiliate', id] });
      toast.add({ title: 'KYC rejected', variant: 'success' });
    },
    onError: () => toast.add({ title: 'Error', description: 'Could not reject KYC', variant: 'error' }),
  });

  if (isLoading || !data) return <p className="text-slate-600">Loading…</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">{data.name}</h1>
      <Card>
        <CardHeader>
          <CardTitle>Affiliate details</CardTitle>
        </CardHeader>
        <div className="space-y-3 p-6 pt-0">
          <p className="text-sm text-slate-600">Email: {data.email}</p>
          <p className="flex items-center gap-2 text-sm text-slate-600">
            KYC: <KycStatusBadge approved={data.kyc_approved_for_payout} />
          </p>
          <div className="flex gap-2">
            <Button onClick={() => approve.mutate()} isLoading={approve.isPending}>
              Approve KYC
            </Button>
            <Button variant="danger" onClick={() => reject.mutate()} isLoading={reject.isPending}>
              Reject KYC
            </Button>
          </div>
          <Link to={`/admin/affiliates/${id}/contract`} className="block text-brand-600 hover:underline">
            Edit contract
          </Link>
        </div>
      </Card>
    </div>
  );
}
