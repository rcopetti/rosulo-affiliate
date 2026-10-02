import { FormEvent, useState } from 'react';
import { Payout, PayoutPaymentConfirmation } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { DataTable, Column } from '@/components/ui/DataTable';
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
  const [selectedPayout, setSelectedPayout] = useState<Payout | null>(null);
  const [paymentMethod, setPaymentMethod] = useState('');
  const [transferReference, setTransferReference] = useState('');

  const closeConfirmation = () => {
    setSelectedPayout(null);
    setPaymentMethod('');
    setTransferReference('');
  };

  const confirmPayment = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedPayout || !paymentMethod.trim() || !transferReference.trim()) return;
    onConfirmPayment(selectedPayout.id, {
      payment_method: paymentMethod.trim(),
      transfer_reference: transferReference.trim(),
    });
    closeConfirmation();
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
            <>
              <Button size="sm" onClick={() => onApprove(p.id)}>
                Approve
              </Button>
              <Button variant="danger" size="sm" onClick={() => onReject(p.id)}>
                Reject
              </Button>
            </>
          )}
          {p.status === 'approved' && (
            <Button
              size="sm"
              aria-label={`Record payment for payout ${p.id}`}
              onClick={() => setSelectedPayout(p)}
            >
              Record payment
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
        open={selectedPayout !== null}
        onClose={closeConfirmation}
        title="Record manual payout"
      >
        {selectedPayout && (
          <form className="space-y-4" onSubmit={confirmPayment}>
            <p className="text-sm text-fg-muted">
              Confirm that {formatCurrency(selectedPayout.net_paid, selectedPayout.currency)} was sent to the affiliate.
            </p>
            <Input
              label="Payment method"
              name="payment_method"
              maxLength={50}
              value={paymentMethod}
              onChange={(event) => setPaymentMethod(event.target.value)}
              required
            />
            <Input
              label="Transfer reference"
              name="transfer_reference"
              maxLength={255}
              value={transferReference}
              onChange={(event) => setTransferReference(event.target.value)}
              required
            />
            <div className="flex justify-end gap-2">
              <Button type="button" variant="secondary" onClick={closeConfirmation}>
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={!paymentMethod.trim() || !transferReference.trim()}
              >
                Confirm payment
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </>
  );
}
