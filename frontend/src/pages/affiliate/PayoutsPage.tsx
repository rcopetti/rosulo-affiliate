import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { getPayouts } from '@/api/affiliate/payouts';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { PayoutsTable } from '@/components/affiliate/PayoutsTable';

export function PayoutsPage() {
  const { data: payouts, isLoading } = useQuery({ queryKey: ['affiliate-payouts'], queryFn: getPayouts });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Payouts</h1>
        <Link to="/affiliate/payouts/request">
          <Button>Request payout</Button>
        </Link>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Payout history</CardTitle>
        </CardHeader>
        {isLoading ? <p className="p-4 text-slate-600">Loading…</p> : <PayoutsTable payouts={payouts || []} />}
      </Card>
    </div>
  );
}
