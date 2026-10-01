import { useQuery } from '@tanstack/react-query';
import { getBalance } from '@/api/affiliate/balance';
import { getCommissions } from '@/api/affiliate/commissions';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { CommissionsTable } from '@/components/affiliate/CommissionsTable';
import { CurrencyBalances } from '@/components/affiliate/CurrencyBalances';

export function BalancePage() {
  const { data: balance, isLoading } = useQuery({ queryKey: ['affiliate-balance'], queryFn: getBalance });
  const { data: commissions } = useQuery({ queryKey: ['affiliate-commissions'], queryFn: () => getCommissions() });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Balance</h1>
      {isLoading || !balance ? (
        <p className="text-slate-600">Loading balance…</p>
      ) : (
        <>
          <CurrencyBalances balance={balance} />
          <Card>
            <CardHeader>
              <CardTitle>Commissions</CardTitle>
            </CardHeader>
            <CommissionsTable commissions={commissions || []} />
          </Card>
        </>
      )}
    </div>
  );
}
