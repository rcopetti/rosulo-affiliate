import { useState } from 'react';
import { Campaign } from '@/api/types';
import { Link } from 'react-router-dom';
import { Check, Copy } from 'lucide-react';
import { DataTable, Column } from '@/components/ui/DataTable';
import { formatDate } from '@/lib/utils';

export function buildCampaignLink(campaign: Campaign): string | null {
  if (!campaign.landing_url) return null;
  try {
    const url = new URL(campaign.landing_url);
    url.searchParams.set('rc', campaign.tracking_code);
    return url.toString();
  } catch {
    return `${campaign.landing_url}?rc=${campaign.tracking_code}`;
  }
}

function CopyCampaignLink({ campaign }: { campaign: Campaign }) {
  const [copied, setCopied] = useState(false);
  const campaignLink = buildCampaignLink(campaign);
  if (!campaignLink) return <span className="text-xs text-fg-muted">-</span>;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(campaignLink);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard unavailable; user can select the text manually.
    }
  };

  return (
    <button
      type="button"
      onClick={copy}
      aria-label={`Copy campaign link for ${campaign.name}`}
      title={campaignLink}
      className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg  bg-surface px-2.5 py-1.5 text-xs font-medium text-fg-muted transition-colors hover:bg-surface-muted hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
    >
      {copied ? <Check className="h-3.5 w-3.5 text-success" aria-hidden="true" /> : <Copy className="h-3.5 w-3.5" aria-hidden="true" />}
    </button>
  );
}

const columns: Column<Campaign>[] = [
  {
    key: 'name',
    header: 'Name',
    render: (c) => (
      <Link
        to={`/affiliate/campaigns/${c.id}`}
        className="font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded"
      >
        {c.name}
      </Link>
    ),
    sortValue: (c) => c.name,
    className: 'max-w-0 w-full truncate',
  },
  {
    key: 'campaign_link',
    header: 'Campaign link',
    render: (c) => (
      <div className="flex items-center gap-2">
        <span className="truncate font-mono text-xs">{buildCampaignLink(c) || '-'}</span>
        <CopyCampaignLink campaign={c} />
      </div>
    ),
    className: 'max-w-0 w-full',
    headerClassName: 'w-35',
  },
  {
    key: 'created_at',
    header: 'Created',
    render: (c) => <span className="whitespace-nowrap text-xs">{formatDate(c.created_at)}</span>,
    sortValue: (c) => new Date(c.created_at).getTime(),
    headerClassName: 'w-32',
  },
];

export function CampaignsTable({ campaigns }: { campaigns: Campaign[] }) {
  return (
    <DataTable
      columns={columns}
      data={campaigns}
      rowKey={(c) => c.id}
      emptyTitle="No campaigns yet"
      emptyDescription="Create your first campaign to start tracking affiliate traffic."
    />
  );
}
