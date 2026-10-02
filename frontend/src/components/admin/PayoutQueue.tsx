import { FormEvent, useState } from 'react';
import { Payout, PayoutPaymentConfirmation } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { DataTable, Column } from '@/components/ui/DataTable';
import { PayoutDetail } from '@/components/admin/PayoutDetail';
import { PayoutStatusBadge } from '@/components/shared/PayoutStatusBadge';
import { formatCurrency, formatDateTime } from '@/lib/utils';
import { Modal } from '@/components/ui/Modal';
import { Input } from '@/components/ui/Input';

interface PayoutQueueProps {
  payouts: Payout[];
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onConfirmPayment: (id: string, details: PayoutPaymentConfirmation) => void;
}

export function PayoutQueue({ payouts, onApprove, onReject, onConfirmPayment }: PayoutQueueProps) {
  const [detailPayout, setDetailPayout] = useState<Payout | null>(null);
  const [paymentPayout, setPaymentPayout] = useState<Payout | null>(null);
  const [paidAt, setPaidAt] = useState('');
  const [transferReference, setTransferReference] = useState('');

  const closePayment = () => {
    setPaymentPayout(null);
    setPaidAt('');
    setTransferReference('');
  };

  const paidAtDate = paidAt ? new Date(paidAt) : null;
  const paidAtValid =
    paidAtDate !== null && !Number.isNaN(paidAtDate.getTime()) && paidAtDate.getTime() <= Date.now();
  const canConfirm = paidAtValid && transferReference.trim().length > 0;

  const confirmPayment = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!paymentPayout || !paidAtDate || !paidAtValid || !transferReference.trim()) return;
    // datetime-local yields a browser-local time; submit it as an ISO-8601
    // timestamp with an explicit offset. Amount, currency, method, and
    // commission membership stay server-derived.
    onConfirmPayment(paymentPayout.id, {
      paid_at: paidAtDate.toISOString(),
      transfer_reference: transferReference.trim(),
    });
    closePayment();
  };

  const columns: Column<Payout>[] = [
    {
      key: 'requested_at',
      header: 'Requested',
      render: (p) => <span className="whitespace-nowrap text-xs">{formatDateTime(p.requested_at)}</span>,
      sortValue: (p) => new Date(p.requested_at).getTime(),
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
          {p.status === 'pending_approval' && (
            <Button size="sm" onClick={() => setDetailPayout(p)}>
              Review
            </Button>
          )}
          {p.status === 'approved' && (
            <Button
              size="sm"
              aria-label={`Record payment for payout ${p.id}`}
              onClick={() => setPaymentPayout(p)}
            >
              Record payment
            </Button>
          )}
          {(p.status === 'paid' || p.status === 'rejected') && (
            <Button variant="secondary" size="sm" onClick={() => setDetailPayout(p)}>
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
        open={detailPayout !== null}
        onClose={() => setDetailPayout(null)}
        title="Payout detail"
        className="max-w-3xl"
      >
        {detailPayout && (
          <div className="space-y-4">
            <PayoutDetail payout={detailPayout} />
            {detailPayout.status === 'pending_approval' && (
              <div className="flex justify-end gap-2 border-t border-line pt-4">
                <Button
                  variant="danger"
                  onClick={() => {
                    onReject(detailPayout.id);
                    setDetailPayout(null);
                  }}
                >
                  Reject
                </Button>
                <Button
                  onClick={() => {
                    onApprove(detailPayout.id);
                    setDetailPayout(null);
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
        open={paymentPayout !== null}
        onClose={closePayment}
        title="Record PayPal payment"
      >
        {paymentPayout && (
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
              <p>
                <span className="font-medium">Payment method:</span> PayPal
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
