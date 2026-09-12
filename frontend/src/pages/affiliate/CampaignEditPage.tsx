import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import { Check, Copy } from 'lucide-react';
import { getCampaign, updateCampaign } from '@/api/affiliate/campaigns';
import { CampaignForm, CampaignFormData } from '@/components/affiliate/CampaignForm';
import { buildCampaignLink } from '@/components/affiliate/CampaignsTable';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { useToast } from '@/components/ui/Toast';

export function CampaignEditPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [copied, setCopied] = useState(false);

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

  const campaignLink = campaign ? buildCampaignLink(campaign) : null;

  const copyLink = async () => {
    if (!campaignLink) return;
    try {
      await navigator.clipboard.writeText(campaignLink);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.add({ title: 'Copy failed', description: 'Could not copy the campaign link', variant: 'error' });
    }
  };

  if (isLoading || !campaign) return <div className="text-sm text-fg-muted">Loading…</div>;

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-2xl font-bold text-fg">Edit campaign</h1>

      <Card>
        <CardHeader>
          <CardTitle>Publication link</CardTitle>
        </CardHeader>
        <div className="space-y-3">
          <div>
            <p className="mb-1 text-sm text-fg-muted">Tracking code</p>
            <p className="font-mono text-sm text-fg">{campaign.tracking_code}</p>
          </div>
          <div>
            <p className="mb-1 text-sm text-fg-muted">Campaign link</p>
            {campaignLink ? (
              <div className="flex items-center gap-2">
                <code className="min-w-0 flex-1 truncate rounded-lg border border-line bg-surface-muted px-3 py-2 font-mono text-xs text-fg">
                  {campaignLink}
                </code>
                <button
                  type="button"
                  onClick={copyLink}
                  aria-label="Copy campaign link"
                  className="inline-flex shrink-0 cursor-pointer items-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-2 text-xs font-medium text-fg transition-colors hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                >
                  {copied ? <Check className="h-4 w-4 text-success" aria-hidden="true" /> : <Copy className="h-4 w-4" aria-hidden="true" />}
                  {copied ? 'Copied' : 'Copy link'}
                </button>
              </div>
            ) : (
              <p className="text-sm text-fg-muted">Add a landing URL to generate the campaign link.</p>
            )}
            <p className="mt-2 text-xs text-fg-muted">
              Share this link in your publications. Traffic from this link is attributed to this campaign.
            </p>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Campaign details</CardTitle>
        </CardHeader>
        <CampaignForm campaign={campaign} onSubmit={(d) => mutation.mutate(d)} isLoading={mutation.isPending} />
      </Card>
    </div>
  );
}
