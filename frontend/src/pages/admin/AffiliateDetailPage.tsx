import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams, Link } from 'react-router-dom';
import { PencilLine } from 'lucide-react';
import { approveKyc, getAffiliate, rejectKyc, viewAffiliateDocument } from '@/api/admin/affiliates';
import { getContract } from '@/api/admin/contracts';
import { Button } from '@/components/ui/Button';
import { PdfViewer } from '@/components/ui/PdfViewer';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { Breadcrumbs } from '@/components/ui/Breadcrumbs';
import { KycStatusBadge } from '@/components/shared/KycStatusBadge';
import { useToast } from '@/components/ui/Toast';
import { formatCurrency } from '@/lib/utils';

export function AffiliateDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [documentPreviewUrl, setDocumentPreviewUrl] = useState<string | null>(null);
  const [documentPreviewType, setDocumentPreviewType] = useState<string | null>(null);
  const [documentPreviewContentType, setDocumentPreviewContentType] = useState<string | null>(null);


  useEffect(() => () => {
    if (documentPreviewUrl) URL.revokeObjectURL(documentPreviewUrl);
  }, [documentPreviewUrl]);
  const { data, isLoading } = useQuery({
    queryKey: ['admin-affiliate', id],
    queryFn: () => getAffiliate(id!),
    enabled: !!id,
  });
  const { data: contract, isLoading: contractLoading } = useQuery({
    queryKey: ['admin-contract', id],
    queryFn: () => getContract(id!),
    enabled: !!id,
    retry: false,
  });

  const approve = useMutation({
    mutationFn: () => approveKyc(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-affiliate', id] });
      toast.add({ title: 'KYC approved', variant: 'success' });
    },
    onError: () => toast.add({ title: 'Error', description: 'Could not approve KYC', variant: 'error' }),
  });

  const reject = useMutation({
    mutationFn: () => rejectKyc(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-affiliate', id] });
      toast.add({ title: 'KYC rejected', variant: 'success' });
    },
    onError: () => toast.add({ title: 'Error', description: 'Could not reject KYC', variant: 'error' }),
  });

  if (isLoading || !data) return <p className="text-sm text-fg-muted">Loading…</p>;

  const terms = contract?.terms ?? [];

  const payoutDetails = [
    { label: 'Email', value: data.email },
    { label: 'Full name', value: data.name },
    { label: 'Country', value: data.country },
    { label: 'State / province', value: data.state },
    { label: 'Postal code', value: data.postal_code },
    { label: 'PayPal account', value: data.paypal_email, mono: true },
  ];
  const taxDetails = [
    { label: 'Tax status', value: data.tax_status === 'foreign_person' ? 'Foreign person' : 'US person' },
    { label: 'Payee type', value: data.tax_entity_type === 'business' ? 'Business/entity' : 'Individual' },
    { label: 'Legal business name', value: data.business_name },
    { label: 'Required document', value: data.tax_form_type },
  ];

  return (
    <div className="space-y-6">
      <Breadcrumbs
        items={[
          { label: 'Affiliates', to: '/admin/affiliates' },
          { label: data.name },
        ]}
      />
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-fg">{data.name}</h1>
        <KycStatusBadge approved={data.kyc_approved_for_payout} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Payout details</CardTitle>
        </CardHeader>
        <p className="-mt-2 mb-4 text-sm text-fg-muted">
          Provided by the affiliate. This information is read-only and is used for the payout process.
        </p>
        <dl className="divide-y divide-line">
          {payoutDetails.map((row) => (
            <div key={row.label} className="flex items-center justify-between gap-4 py-2.5">
              <dt className="text-sm text-fg-muted">{row.label}</dt>
              <dd className={row.mono ? 'font-mono text-sm text-fg' : 'text-sm font-medium text-fg'}>
                {row.value?.trim() ? row.value : '—'}
              </dd>
            </div>
          ))}
        </dl>
        <div className="mt-4 flex gap-2">
          <Button onClick={() => approve.mutate()} isLoading={approve.isPending}>
            Approve KYC
          </Button>
          <Button variant="danger" onClick={() => reject.mutate()} isLoading={reject.isPending}>
            Reject KYC
          </Button>
        </div>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Tax documents</CardTitle>
        </CardHeader>
        {data.documents?.length ? (
          <div className="space-y-2">
            {data.documents.map((document) => (
              <div key={document.id} className="flex items-center justify-between gap-4 rounded-lg border border-line p-3">
                <div>
                  <p className="text-sm font-medium text-fg">{document.document_type}</p>
                  <p className="text-xs text-fg-muted">{document.approved ? 'Approved' : 'Pending review'}</p>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={async () => {
                    try {
                      const preview = await viewAffiliateDocument(id!, document.id);
                      setDocumentPreviewUrl(preview.url);
                      setDocumentPreviewContentType(preview.contentType);
                      setDocumentPreviewType(document.document_type);
                    } catch {
                      toast.add({ title: 'Preview failed', description: 'Could not load the encrypted document', variant: 'error' });
                    }
                  }}
                >
                  View securely
                </Button>
              </div>
            ))}
          </div>
        ) : <p className="text-sm text-fg-muted">No tax documents uploaded.</p>}
        {documentPreviewUrl && (
          <div className="mt-4 overflow-hidden rounded-lg border border-line">
            <div className="border-b border-line px-3 py-2 text-xs font-medium text-fg-muted">Secure preview: {documentPreviewType}</div>
            {documentPreviewContentType === 'application/pdf' ? (
              <PdfViewer url={documentPreviewUrl} title="Secure tax document preview" />
            ) : (
              <img src={documentPreviewUrl} alt="Secure tax document preview" className="max-h-[32rem] w-full object-contain" />
            )}
          </div>
        )}
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Tax classification</CardTitle>
        </CardHeader>
        <dl className="divide-y divide-line">
          {taxDetails.map((row) => (
            <div key={row.label} className="flex items-center justify-between gap-4 py-2.5">
              <dt className="text-sm text-fg-muted">{row.label}</dt>
              <dd className="text-sm font-medium text-fg">{row.value?.trim() ? row.value : '—'}</dd>
            </div>
          ))}
        </dl>
      </Card>

      <Card>
        <CardHeader
          action={
            <Link to={`/admin/affiliates/${id}/contract`}>
              <Button variant="secondary" size="sm">
                <PencilLine className="h-4 w-4" aria-hidden="true" />
                Edit terms
              </Button>
            </Link>
          }
        >
          <CardTitle>Contract terms</CardTitle>
        </CardHeader>
        {contractLoading ? (
          <p className="text-sm text-fg-muted">Loading terms…</p>
        ) : terms.length === 0 ? (
          <p className="text-sm text-fg-muted">No terms configured yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wider text-fg-muted">
                <th scope="col" className="py-2 pr-4 font-semibold">Payment sequence</th>
                <th scope="col" className="py-2 pr-4 font-semibold">Commission</th>
                <th scope="col" className="py-2 pr-4 font-semibold">Min. threshold</th>
                <th scope="col" className="py-2 font-semibold">Effective</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {terms.map((t) => (
                <tr key={t.id}>
                  <td className="py-2.5 pr-4">{t.payment_sequence ?? 'Any'}</td>
                  <td className="py-2.5 pr-4 tabular-nums">{t.commission_percent}%</td>
                  <td className="py-2.5 pr-4 tabular-nums">
                    {t.minimum_threshold != null ? formatCurrency(t.minimum_threshold) : '—'}
                  </td>
                  <td className="py-2 text-xs text-fg-muted">
                    {t.effective_from || '—'} → {t.effective_to || 'open'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="mt-4">
          <Link
            to={`/admin/affiliates/${id}/contract`}
            className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
          >
            <PencilLine className="h-4 w-4" aria-hidden="true" />
            Edit contract
          </Link>
        </div>
      </Card>
    </div>
  );
}
