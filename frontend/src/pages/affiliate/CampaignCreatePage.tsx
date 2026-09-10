import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { createCampaign } from '@/api/affiliate/campaigns';
import { CampaignForm, CampaignFormData } from '@/components/affiliate/CampaignForm';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { useToast } from '@/components/ui/Toast';

export function CampaignCreatePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();

  const mutation = useMutation({
    mutationFn: createCampaign,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['affiliate-campaigns'] });
      toast.add({ title: 'Campaign created', variant: 'success' });
      navigate('/affiliate/campaigns');
    },
    onError: () => toast.add({ title: 'Error', description: 'Could not create campaign', variant: 'error' }),
  });

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-2xl font-bold text-slate-900">New campaign</h1>
      <Card>
        <CardHeader>
          <CardTitle>Campaign details</CardTitle>
        </CardHeader>
        <CampaignForm onSubmit={(d: CampaignFormData) => mutation.mutate(d)} isLoading={mutation.isPending} />
      </Card>
    </div>
  );
}
