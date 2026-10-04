import { useEffect, useState } from 'react';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams, Link } from 'react-router-dom';
import { PencilLine } from 'lucide-react';
import { getAffiliate, getAffiliatePayouts, reviewAffiliateDocument, viewAffiliateDocument } from '@/api/admin/affiliates';
import { getContract } from '@/api/admin/contracts';
import { Button } from '@/components/ui/Button';
import { PdfViewer } from '@/components/ui/PdfViewer';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { Breadcrumbs } from '@/components/ui/Breadcrumbs';
import { KycStatusBadge } from '@/components/shared/KycStatusBadge';
import { PayoutStatusBadge } from '@/components/shared/PayoutStatusBadge';
import { useToast } from '@/components/ui/Toast';
import { formatCurrency, formatDateTime } from '@/lib/utils';

const PAYOUT_PAGE_SIZE = 20;

export function AffiliateDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [payoutOffset, setPayoutOffset] = useState(0);
  const [documentPreviewUrl, setDocumentPreviewUrl] = useState<string | null>(null);
  const [documentPreviewType, setDocumentPreviewType] = useState<string | null>(null);
  const [documentPreviewContentType, setDocumentPreviewContentType] = useState<string | null>(null);
  const [rejectionReasons, setRejectionReasons] = useState<Record<string, string>>({});
  const [reviewOpen, setReviewOpen] = useState<Record<string, boolean>>({});

  useEffect(() => () => {
    if (documentPreviewUrl) URL.revokeObjectURL(documentPreviewUrl);
  }, [documentPreviewUrl]);
  useEffect(() => setPayoutOffset(0), [id]);
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
  const { data: payoutHistory, isError: payoutHistoryError } = useQuery({
    queryKey: ['admin-affiliate-payouts', id, payoutOffset],
    queryFn: () => getAffiliatePayouts(id!, { limit: PAYOUT_PAGE_SIZE, offset: payoutOffset }),
    enabled: !!id,
    retry: false,
    placeholderData: keepPreviousData,
  });

  const review = useMutation({
    mutationFn: ({ documentId, status, rejectionReason }: {
      documentId: string;
      status: 'approved' | 'rejected';
      rejectionReason?: string;
    }) => reviewAffiliateDocument(id!, documentId, {
      status,
      rejection_reason: rejectionReason,
    }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['admin-affiliate', id] });
      toast.add({
        title: variables.status === 'approved' ? 'Tax document approved' : 'Tax document rejected',
        variant: 'success',
      });
    },
    onError: () => toast.add({ title: 'Error', description: 'Could not review tax document', variant: 'error' }),
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
        <KycStatusBadge status={data.payout_eligibility.status} />
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
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Payout history</CardTitle>
        </CardHeader>
        {payoutHistoryError ? (
          <p className="text-sm text-fg-muted">Could not load payout history.</p>
        ) : payoutHistory === undefined ? (
          <p className="text-sm text-fg-muted">Loading payouts…</p>
        ) : (
          <>
            {payoutHistory.paid_totals_by_currency.length > 0 && (
              <table className="mb-4 w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs uppercase tracking-wider text-fg-muted">
                    <th scope="col" className="py-2 pr-4 font-semibold">Currency</th>
                    <th scope="col" className="py-2 pr-4 font-semibold">Paid last 12 months</th>
                    <th scope="col" className="py-2 font-semibold">Paid year to date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {payoutHistory.paid_totals_by_currency.map((row) => (
                    <tr key={row.currency}>
                      <td className="py-2.5 pr-4 font-medium text-fg">{row.currency}</td>
                      <td className="py-2.5 pr-4 tabular-nums">{formatCurrency(row.rolling_12_months, row.currency)}</td>
                      <td className="py-2.5 tabular-nums">{formatCurrency(row.year_to_date, row.currency)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {payoutHistory.items.length === 0 ? (
              <p className="text-sm text-fg-muted">No payouts yet.</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs uppercase tracking-wider text-fg-muted">
                    <th scope="col" className="py-2 pr-4 font-semibold">Requested</th>
                    <th scope="col" className="py-2 pr-4 font-semibold">Paid</th>
                    <th scope="col" className="py-2 pr-4 font-semibold">Status</th>
                    <th scope="col" className="py-2 pr-4 font-semibold">Gross</th>
                    <th scope="col" className="py-2 pr-4 font-semibold">Net</th>
                    <th scope="col" className="py-2 font-semibold">Reference</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {payoutHistory.items.map((payout) => (
                    <tr key={payout.id}>
                      <td className="py-2.5 pr-4 text-fg-muted">{formatDateTime(payout.requested_at)}</td>
                      <td className="py-2.5 pr-4 text-fg-muted">{payout.paid_at ? formatDateTime(payout.paid_at) : '—'}</td>
                      <td className="py-2.5 pr-4"><PayoutStatusBadge status={payout.status} /></td>
                      <td className="py-2.5 pr-4 tabular-nums">{formatCurrency(payout.requested_amount, payout.currency)}</td>
                      <td className="py-2.5 pr-4 tabular-nums">{formatCurrency(payout.net_paid, payout.currency)}</td>
                      <td className="py-2.5 font-mono text-xs text-fg-muted">{payout.payment_reference || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {payoutHistory.total > PAYOUT_PAGE_SIZE && (
              <div className="mt-4 flex items-center justify-between">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={payoutOffset === 0}
                  onClick={() => setPayoutOffset(Math.max(0, payoutOffset - PAYOUT_PAGE_SIZE))}
                >
                  Previous
                </Button>
                <span className="text-xs text-fg-muted">
                  {payoutOffset + 1}–{Math.min(payoutOffset + PAYOUT_PAGE_SIZE, payoutHistory.total)} of {payoutHistory.total}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={payoutOffset + PAYOUT_PAGE_SIZE >= payoutHistory.total}
                  onClick={() => setPayoutOffset(payoutOffset + PAYOUT_PAGE_SIZE)}
                >
                  Next
                </Button>
              </div>
            )}
          </>
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
        <CardHeader>
          <CardTitle>Tax documents</CardTitle>
        </CardHeader>
        {data.documents?.length ? (
          <div className="space-y-2">
            {[...data.documents]
              .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
              .map((document, index) => (
                <div key={document.id} className="space-y-3 rounded-lg border border-line p-3">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-sm font-medium text-fg">
                        {document.document_type}
                        {index === 0 && <span className="ml-2 rounded-full bg-info-soft px-2 py-0.5 text-[10px] font-medium text-info-fg">Most recent</span>}
                      </p>
                      <p className="text-xs text-fg-muted">
                        Submitted {formatDateTime(document.created_at)} · {document.status === 'approved' ? 'Approved' : document.status === 'rejected' ? 'Rejected' : 'Pending review'}
                      </p>
                      {document.review_history.map((review, reviewIndex) => (
                        <p key={`${document.id}-${reviewIndex}`} className="mt-1 text-xs text-fg-muted">
                          Reviewed {formatDateTime(review.reviewed_at)} by {review.reviewer.name || review.reviewer.email}: {review.status}
                          {review.rejection_reason ? ` · ${review.rejection_reason}` : ''}
                        </p>
                      ))}
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={async () => {
                          try {
                            const preview = await viewAffiliateDocument(id!, document.id);
                            setDocumentPreviewUrl(preview.url);
                            setDocumentPreviewContentType(preview.contentType);
                            setDocumentPreviewType(document.content_type);
                          } catch {
                            toast.add({ title: 'Preview failed', description: 'Could not load the encrypted document', variant: 'error' });
                          }
                        }}
                      >
                        View securely
                      </Button>
                      {document.status !== 'pending' && (
                        <Button
                          variant="secondary"
                          size="sm"
                          aria-expanded={!!reviewOpen[document.id]}
                          onClick={() =>
                            setReviewOpen((current) => ({
                              ...current,
                              [document.id]: !current[document.id],
                            }))
                          }
                        >
                          Review
                        </Button>
                      )}
                    </div>
                  </div>
                  {(document.status === 'pending' || reviewOpen[document.id]) && (
                    <>
                      <label className="block text-xs text-fg-muted">
                        Rejection reason
                        <textarea
                          aria-label={`Rejection reason for ${document.document_type}`}
                          className="mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-fg"
                          rows={2}
                          value={rejectionReasons[document.id] || ''}
                          onChange={(event) => setRejectionReasons((current) => ({ ...current, [document.id]: event.target.value }))}
                        />
                      </label>
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          onClick={() => review.mutate({ documentId: document.id, status: 'approved' })}
                          isLoading={review.isPending}
                        >
                          Approve tax form
                        </Button>
                        <Button
                          variant="danger"
                          size="sm"
                          disabled={!rejectionReasons[document.id]?.trim()}
                          onClick={() => review.mutate({
                            documentId: document.id,
                            status: 'rejected',
                            rejectionReason: (rejectionReasons[document.id] || '').trim(),
                          })}
                          isLoading={review.isPending}
                        >
                          Reject tax form
                        </Button>
                      </div>
                    </>
                  )}
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
