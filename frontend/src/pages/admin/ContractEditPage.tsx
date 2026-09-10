import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { getContract, updateContract } from '@/api/admin/contracts';
import { ContractForm } from '@/components/admin/ContractForm';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { useToast } from '@/components/ui/Toast';
import { Term } from '@/api/types';

export function ContractEditPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const toast = useToast();

  const { data: contract, isLoading } = useQuery({
    queryKey: ['admin-contract', id],
    queryFn: () => getContract(id!),
    enabled: !!id,
  });

  const mutation = useMutation({
    mutationFn: (data: { terms: Term[] }) =>
      updateContract(id!, {
        id: contract?.id || '',
        affiliate_id: id!,
        terms: data.terms.map((t) => ({
          ...t,
          commission_percent: Number(t.commission_percent),
          minimum_threshold: t.minimum_threshold ? Number(t.minimum_threshold) : undefined,
        })),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-contract', id] });
      toast.add({ title: 'Contract saved', variant: 'success' });
    },
    onError: () => toast.add({ title: 'Error', description: 'Could not save contract', variant: 'error' }),
  });

  if (isLoading || !contract) return <p className="text-slate-600">Loading contract…</p>;

  return (
    <div className="max-w-3xl space-y-4">
      <h1 className="text-2xl font-bold text-slate-900">Edit contract</h1>
      <Card>
        <CardHeader>
          <CardTitle>Terms</CardTitle>
        </CardHeader>
        <ContractForm terms={contract.terms} onSubmit={(d) => mutation.mutate(d)} isLoading={mutation.isPending} />
      </Card>
    </div>
  );
}
