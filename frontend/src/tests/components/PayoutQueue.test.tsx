import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Payout } from '@/api/types';
import { PayoutQueue } from '@/components/admin/PayoutQueue';

const payout: Payout = {
  id: 'payout-1',
  affiliate_id: 'affiliate-1',
  requested_amount: 100,
  approved_amount: 100,
  withholding_total: 0,
  paypal_fees: 0,
  net_paid: 100,
  currency: 'USD',
  status: 'approved',
  requested_at: '2026-10-01T00:00:00Z',
};

describe('PayoutQueue', () => {
  it('confirms an approved payout with a payment method and transfer reference', () => {
    const onConfirmPayment = vi.fn();
    const props = {
      payouts: [payout],
      onApprove: () => undefined,
      onReject: () => undefined,
      onConfirmPayment,
    };
    render(<PayoutQueue {...props} />);

    fireEvent.click(screen.getByRole('button', { name: /record payment/i }));
    fireEvent.change(screen.getByLabelText(/Payment method/), { target: { value: 'bank_transfer' } });
    fireEvent.change(screen.getByLabelText(/Transfer reference/), { target: { value: 'bank-tx-123' } });
    fireEvent.click(screen.getByRole('button', { name: /confirm payment/i }));

    expect(onConfirmPayment).toHaveBeenCalledWith('payout-1', {
      payment_method: 'bank_transfer',
      transfer_reference: 'bank-tx-123',
    });
  });
});
