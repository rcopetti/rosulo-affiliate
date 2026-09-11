import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import { getCampaign, updateCampaign } from '@/api/affiliate/campaigns';
import { CampaignForm, CampaignFormData } from '@/components/affiliate/CampaignForm';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { useToast } from '@/components/ui/Toast';

export function CampaignEditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();

  const { data: campaign, isLoading } = useQuery({
    queryKey: ['affiliate-campaign', id],
    queryFn: () => getCampaign(id!),
    enabled: !!id,
  });

  const mutation = useMutation({
    mutationFn: (data: CampaignFormData) => updateCampaign(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['affiliate-campaigns'] });
      toast.add({ title: 'Campaign updated', variant: 'success' });
      navigate('/affiliate/campaigns');
    },
    onError: () => toast.add({ title: 'Error', description: 'Could not update campaign', variant: 'error' }),
  });

  if (isLoading || !campaign) return <div className="p-4 text-slate-600">Loading…</div>;

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-2xl font-bold text-slate-900">Edit campaign</h1>
      <Card>
        <CardHeader>
          <CardTitle>Campaign details</CardTitle>
        </CardHeader>
        <CampaignForm campaign={campaign} onSubmit={(d) => mutation.mutate(d)} isLoading={mutation.isPending} />
      </Card>
    </div>
  );
}
