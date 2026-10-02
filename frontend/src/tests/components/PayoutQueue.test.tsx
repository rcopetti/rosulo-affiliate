import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Payout } from '@/api/types';
import { PayoutQueue } from '@/components/admin/PayoutQueue';

const approvedPayout: Payout = {
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
  affiliate: {
    name: 'Ada Affiliate',
    email: 'ada@example.com',
    paypal_email: 'ada-paypal@example.com',
  },
  payout_commissions: [
    {
      commission_id: 'commission-1',
      event_id: 'event-1',
      occurred_at: '2026-09-20T12:00:00Z',
      good_date: '2026-09-20',
      payment_sequence: 1,
      gross_amount: 60,
      withholding_amount: 0,
      net_amount: 60,
      currency: 'USD',
      campaign_id: 'campaign-1',
    },
    {
      commission_id: 'commission-2',
      event_id: 'event-2',
      occurred_at: '2026-09-25T08:30:00Z',
      good_date: '2026-09-22',
      payment_sequence: 2,
      gross_amount: 40,
      withholding_amount: 0,
      net_amount: 40,
      currency: 'USD',
      campaign_id: 'campaign-1',
    },
  ],
  commission_count: 2,
  earliest_sale_at: '2026-09-20T12:00:00Z',
  latest_sale_at: '2026-09-25T08:30:00Z',
};

const pendingPayout: Payout = { ...approvedPayout, id: 'payout-2', status: 'pending_approval' };

function renderQueue(payout: Payout, overrides: Partial<Parameters<typeof PayoutQueue>[0]> = {}) {
  const props = {
    payouts: [payout],
    onApprove: vi.fn(),
    onReject: vi.fn(),
    onConfirmPayment: vi.fn(),
    ...overrides,
  };
  render(<PayoutQueue {...props} />);
  return props;
}

describe('PayoutQueue', () => {
  it('shows the payee identity, net amount, and commission count in the payment modal', () => {
    renderQueue(approvedPayout);

    fireEvent.click(screen.getByRole('button', { name: /record payment/i }));

    expect(screen.getAllByText('Ada Affiliate').length).toBeGreaterThan(0);
    expect(screen.getByText('ada@example.com')).toBeInTheDocument();
    expect(screen.getByText('ada-paypal@example.com')).toBeInTheDocument();
    expect(screen.getAllByText('$100.00').length).toBeGreaterThan(0);
    expect(screen.getByText(/2\s*commissions/)).toBeInTheDocument();
    // Amount/currency/method are read-only: no editable inputs for them.
    expect(screen.queryByLabelText(/^payment method$/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/^amount$/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/^currency$/i)).not.toBeInTheDocument();
  });

  it('confirms an approved payout with only a paid datetime and PayPal reference', () => {
    const onConfirmPayment = vi.fn();
    renderQueue(approvedPayout, { onConfirmPayment });

    fireEvent.click(screen.getByRole('button', { name: /record payment/i }));
    fireEvent.change(screen.getByLabelText(/Paid at/), {
      target: { value: '2026-09-30T10:30' },
    });
    fireEvent.change(screen.getByLabelText(/PayPal transaction reference/), {
      target: { value: 'PP-TX-123' },
    });
    fireEvent.click(screen.getByRole('button', { name: /confirm payment/i }));

    // The browser-local datetime-local value is converted to ISO-8601 with an offset.
    expect(onConfirmPayment).toHaveBeenCalledWith('payout-1', {
      paid_at: new Date('2026-09-30T10:30').toISOString(),
      transfer_reference: 'PP-TX-123',
    });
  });

  it('blocks confirmation when the datetime or reference is blank', () => {
    renderQueue(approvedPayout);

    fireEvent.click(screen.getByRole('button', { name: /record payment/i }));
    const confirm = screen.getByRole('button', { name: /confirm payment/i });
    expect(confirm).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/Paid at/), {
      target: { value: '2026-09-30T10:30' },
    });
    expect(confirm).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/PayPal transaction reference/), {
      target: { value: 'PP-TX-123' },
    });
    expect(confirm).toBeEnabled();
  });

  it('opens the itemized detail for pending payouts before approval or rejection', () => {
    const onApprove = vi.fn();
    const onReject = vi.fn();
    renderQueue(pendingPayout, { onApprove, onReject });

    fireEvent.click(screen.getByRole('button', { name: /review/i }));

    // Payee identity, commission count, totals, and the source-sale window.
    expect(screen.getAllByText('Ada Affiliate').length).toBeGreaterThan(0);
    expect(screen.getByText('ada-paypal@example.com')).toBeInTheDocument();
    expect(screen.getByText(/2\s*commissions/)).toBeInTheDocument();
    expect(screen.getAllByText('$100.00').length).toBeGreaterThan(0);
    expect(screen.getByText(/sales from/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /^approve$/i }));
    expect(onApprove).toHaveBeenCalledWith('payout-2');
    expect(onReject).not.toHaveBeenCalled();
  });

  it('rejects a pending payout from the detail review', () => {
    const onReject = vi.fn();
    renderQueue(pendingPayout, { onReject });

    fireEvent.click(screen.getByRole('button', { name: /review/i }));
    fireEvent.click(screen.getByRole('button', { name: /^reject$/i }));

    expect(onReject).toHaveBeenCalledWith('payout-2');
  });
});
