import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { fetchMerchants, selectMerchant } from '@/api/auth';
import { useAuthStore } from '@/store/auth';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { useToast } from '@/components/ui/Toast';

export function MerchantSelectPage() {
  const navigate = useNavigate();
  const setTenant = useAuthStore((s) => s.setTenant);
  const toast = useToast();

  const { data: merchants, isLoading } = useQuery({
    queryKey: ['merchants'],
    queryFn: fetchMerchants,
  });

  const handleSelect = async (tenantId: string) => {
    try {
      await selectMerchant(tenantId);
      setTenant(tenantId);
      navigate('/affiliate/dashboard');
    } catch {
      toast.add({ title: 'Selection failed', description: 'Could not select merchant', variant: 'error' });
    }
  };

  if (isLoading) return <div className="p-8 text-center">Loading merchants…</div>;

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <CardTitle>Select a Merchant</CardTitle>
        </CardHeader>
        <div className="space-y-2">
          {merchants?.length ? (
            merchants.map((m) => (
              <button
                key={m.id}
                onClick={() => handleSelect(m.id)}
                className="w-full cursor-pointer rounded-lg border border-line bg-surface p-4 text-left transition hover:border-primary hover:shadow-sm"
              >
                <p className="font-semibold text-slate-900">{m.name}</p>
              </button>
            ))
          ) : (
            <p className="text-sm text-slate-600">You are not linked to any merchants yet.</p>
          )}
        </div>
      </Card>
    </div>
  );
}
