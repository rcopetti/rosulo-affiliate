import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { createAffiliate } from '@/api/admin/affiliates';
import { AffiliateForm, AffiliateFormData } from '@/components/admin/AffiliateForm';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { useToast } from '@/components/ui/Toast';

export function AffiliateCreatePage() {
  const navigate = useNavigate();
  const toast = useToast();

  const mutation = useMutation({
    mutationFn: (data: AffiliateFormData) =>
      createAffiliate({
        ...data,
        contract: { terms: [{ payment_sequence: '1', commission_percent: 10 }] },
      }),
    onSuccess: () => {
      toast.add({ title: 'Affiliate created', variant: 'success' });
      navigate('/admin/affiliates');
    },
    onError: () => toast.add({ title: 'Error', description: 'Could not create affiliate', variant: 'error' }),
  });

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-2xl font-bold text-slate-900">Create affiliate</h1>
      <Card>
        <CardHeader>
          <CardTitle>Affiliate details</CardTitle>
        </CardHeader>
        <AffiliateForm onSubmit={(d) => mutation.mutate(d)} isLoading={mutation.isPending} />
      </Card>
    </div>
  );
}
