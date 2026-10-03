import { FormEvent, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ExternalLink } from 'lucide-react';
import { getAdminPayout } from '@/api/admin/payouts';
import { PayoutPaymentConfirmation, PayoutQueueItem } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { DataTable, Column } from '@/components/ui/DataTable';
import { PayoutDetail } from '@/components/admin/PayoutDetail';
import { PayoutStatusBadge } from '@/components/shared/PayoutStatusBadge';
import { formatCurrency, formatDateTime } from '@/lib/utils';
import { Modal } from '@/components/ui/Modal';
import { Input } from '@/components/ui/Input';

interface PayoutQueueProps {
  payouts: PayoutQueueItem[];
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onConfirmPayment: (id: string, details: PayoutPaymentConfirmation) => void;
  onRetryNotification?: (id: string) => void;
  isRetryPending?: boolean;
}

function usePayoutDetail(id: string | null) {
  return useQuery({
    queryKey: ['admin-payout', id],
    queryFn: () => getAdminPayout(id as string),
    enabled: id !== null,
  });
}

function PayoutLoading() {
  return <p className="text-sm text-fg-muted">Loading…</p>;
}

function paypalSendUrl(recipient: string, amount: number, currency: string) {
  const params = new URLSearchParams({
    recipient,
    amount: amount.toFixed(2),
    currencyCode: currency,
  });
  return `https://www.paypal.com/myaccount/transfer/send/external?${params}`;
}

export function PayoutQueue({ payouts, onApprove, onReject, onConfirmPayment, onRetryNotification, isRetryPending }: PayoutQueueProps) {
  const [detailId, setDetailId] = useState<string | null>(null);
  const [paymentId, setPaymentId] = useState<string | null>(null);
  const [paidAt, setPaidAt] = useState('');
  const [transferReference, setTransferReference] = useState('');

  // Modals always load the full payout by id: the queue row is intentionally
  // sparse (the dashboard feeds a lean projection), and fetching fresh detail
  // keeps the modal honest if the row changed since it was rendered.
  const { data: detailPayout, isLoading: detailLoading } = usePayoutDetail(detailId);
  const { data: paymentPayout, isLoading: paymentLoading } = usePayoutDetail(paymentId);

  const closePayment = () => {
    setPaymentId(null);
    setPaidAt('');
    setTransferReference('');
  };

  const paidAtDate = paidAt ? new Date(paidAt) : null;
  const paidAtValid =
    paidAtDate !== null && !Number.isNaN(paidAtDate.getTime()) && paidAtDate.getTime() <= Date.now();
  const canConfirm = paidAtValid && transferReference.trim().length > 0;

  const confirmPayment = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!paymentId || !paidAtDate || !paidAtValid || !transferReference.trim()) return;
    // datetime-local yields a browser-local time; submit it as an ISO-8601
    // timestamp with an explicit offset. Amount, currency, method, and
    // commission membership stay server-derived.
    onConfirmPayment(paymentId, {
      paid_at: paidAtDate.toISOString(),
      transfer_reference: transferReference.trim(),
    });
    closePayment();
  };

  const columns: Column<PayoutQueueItem>[] = [
    {
      key: 'requested_at',
      header: 'Requested',
      render: (p) => (
        <span className="whitespace-nowrap text-xs">
          {p.requested_at ? formatDateTime(p.requested_at) : '—'}
        </span>
      ),
      sortValue: (p) => (p.requested_at ? new Date(p.requested_at).getTime() : 0),
      headerClassName: 'w-44',
    },
    {
      key: 'affiliate',
      header: 'Affiliate',
      render: (p) => <span className="whitespace-nowrap">{p.affiliate?.name ?? '—'}</span>,
      headerClassName: 'w-40',
    },
    {
      key: 'requested_amount',
      header: 'Amount',
      render: (p) => <span className="whitespace-nowrap">{formatCurrency(p.requested_amount, p.currency)}</span>,
      sortValue: (p) => p.requested_amount,
      className: 'text-right whitespace-nowrap',
      headerClassName: 'w-32 text-right',
    },
    {
      key: 'status',
      header: 'Status',
      render: (p) => <PayoutStatusBadge status={p.status} />,
      headerClassName: 'w-36',
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (p) => (
        <div className="flex gap-2">
          {p.status === 'approved' && (
            <Button
              size="sm"
              aria-label={`Record payment for payout ${p.id}`}
              onClick={() => setPaymentId(p.id)}
            >
              Record payment
            </Button>
          )}
          {p.status === 'pending_approval' ? (
            <Button size="sm" onClick={() => setDetailId(p.id)}>
              Review
            </Button>
          ) : (
            <Button variant="secondary" size="sm" onClick={() => setDetailId(p.id)}>
              View
            </Button>
          )}
        </div>
      ),
      headerClassName: 'w-44',
    },
  ];

  return (
    <>
      <DataTable
        columns={columns}
        data={payouts}
        rowKey={(p) => p.id}
        emptyTitle="Payout queue is empty"
        emptyDescription="Payout requests from affiliates will appear here for approval."
      />

      <Modal
        open={detailId !== null}
        onClose={() => setDetailId(null)}
        title="Payout detail"
        className="max-w-3xl"
      >
        {detailLoading || !detailPayout ? (
          <PayoutLoading />
        ) : (
          <div className="space-y-4">
            <PayoutDetail payout={detailPayout} onRetryNotification={onRetryNotification} isRetryPending={isRetryPending} />
            {detailPayout.status === 'pending_approval' && (
              <div className="flex justify-end gap-2 border-t border-line pt-4">
                <Button
                  variant="danger"
                  onClick={() => {
                    onReject(detailPayout.id);
                    setDetailId(null);
                  }}
                >
                  Reject
                </Button>
                <Button
                  onClick={() => {
                    onApprove(detailPayout.id);
                    setDetailId(null);
                  }}
                >
                  Approve
                </Button>
              </div>
            )}
          </div>
        )}
      </Modal>

      <Modal
        open={paymentId !== null}
        onClose={closePayment}
        title="Record PayPal payment"
      >
        {paymentLoading || !paymentPayout ? (
          <PayoutLoading />
        ) : (
          <form className="space-y-4" onSubmit={confirmPayment}>
            <p className="text-sm text-fg-muted">
              Confirm the PayPal transfer for this payout. Amount, currency, method, and
              commission membership are fixed by the approved payout.
            </p>
            <div className="space-y-1 rounded-md bg-surface-muted p-3 text-sm text-slate-700">
              {paymentPayout.affiliate && (
                <>
                  <p>
                    <span className="font-medium">Affiliate:</span> {paymentPayout.affiliate.name}
                  </p>
                  <p>
                    <span className="font-medium">Email:</span> {paymentPayout.affiliate.email}
                  </p>
                </>
              )}
              <p>
                <span className="font-medium">PayPal email:</span>{' '}
                {paymentPayout.affiliate?.paypal_email ?? '—'}
              </p>
              <p>
                <span className="font-medium">Net payout:</span>{' '}
                {formatCurrency(paymentPayout.net_paid, paymentPayout.currency)}
              </p>
              <p className="flex items-center gap-2">
                <span className="font-medium">Payment method:</span> PayPal
                {paymentPayout.affiliate?.paypal_email && (
                  <a
                    href={paypalSendUrl(
                      paymentPayout.affiliate.paypal_email,
                      paymentPayout.net_paid,
                      paymentPayout.currency
                    )}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 rounded-md border border-line bg-surface px-2 py-0.5 text-xs font-medium text-primary transition-colors hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                  >
                    Pay in PayPal
                    <ExternalLink className="h-3 w-3" aria-hidden="true" />
                  </a>
                )}
              </p>
              <p>
                <span className="font-medium">Commissions:</span>{' '}
                {paymentPayout.commission_count ?? paymentPayout.payout_commissions?.length ?? 0}{' '}
                {(paymentPayout.commission_count ?? paymentPayout.payout_commissions?.length ?? 0) ===
                1
                  ? 'commission'
                  : 'commissions'}
              </p>
            </div>
            <Input
              label="Paid at"
              name="paid_at"
              type="datetime-local"
              value={paidAt}
              onChange={(event) => setPaidAt(event.target.value)}
              required
            />
            <Input
              label="PayPal transaction reference"
              name="transfer_reference"
              maxLength={255}
              value={transferReference}
              onChange={(event) => setTransferReference(event.target.value)}
              required
            />
            <div className="flex justify-end gap-2">
              <Button type="button" variant="secondary" onClick={closePayment}>
                Cancel
              </Button>
              <Button type="submit" disabled={!canConfirm}>
                Confirm payment
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </>
  );
}
