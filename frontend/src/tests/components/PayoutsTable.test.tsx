import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Payout } from '@/api/types';
import { PayoutsTable } from '@/components/affiliate/PayoutsTable';

const payout: Payout = {
  id: 'payout-1',
  affiliate_id: 'affiliate-1',
  requested_amount: 100,
  approved_amount: 100,
  withholding_total: 0,
  paypal_fees: 0,
  net_paid: 100,
  currency: 'USD',
  status: 'paid',
  requested_at: '2026-10-01T00:00:00Z',
  payout_payment: {
    id: 'payment-1',
    payout_id: 'payout-1',
    amount: 100,
    currency: 'USD',
    payment_method: 'paypal',
    transfer_reference: 'bank-tx-123',
    paid_at: '2026-10-01T00:00:00Z',
    recorded_by_tenant_user_id: 'tenant-user-1',
  },
};

describe('PayoutsTable', () => {
  it('shows the manual transfer reference for a completed payout', () => {
    render(<PayoutsTable payouts={[payout]} />);

    expect(screen.getByText('bank-tx-123')).toBeInTheDocument();
  });
});
