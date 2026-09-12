import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { getCampaigns } from '@/api/affiliate/campaigns';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { CampaignsTable } from '@/components/affiliate/CampaignsTable';

export function CampaignsPage() {
  const { data: campaigns, isLoading } = useQuery({ queryKey: ['affiliate-campaigns'], queryFn: getCampaigns });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Campaigns</h1>
        <Link to="/affiliate/campaigns/new">
          <Button>New campaign</Button>
        </Link>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Your campaigns</CardTitle>
        </CardHeader>
        {isLoading ? <p className="text-sm text-fg-muted">Loading…</p> : <CampaignsTable campaigns={campaigns || []} />}
      </Card>
    </div>
  );
}
