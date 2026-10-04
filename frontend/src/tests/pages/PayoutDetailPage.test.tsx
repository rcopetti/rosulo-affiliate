import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AxiosError, AxiosHeaders } from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { getPayout } from '@/api/affiliate/payouts';
import { PayoutDetailPage } from '@/pages/affiliate/PayoutDetailPage';
import type { Payout } from '@/api/types';

vi.mock('@/api/affiliate/payouts', () => ({ getPayout: vi.fn() }));

const paidPayout: Payout = {
  id: 'payout-1',
  affiliate_id: 'affiliate-1',
  tenant_id: 'tenant-1',
  requested_amount: 100,
  approved_amount: 100,
  withholding_total: 10,
  paypal_fees: 0,
  net_paid: 90,
  currency: 'USD',
  status: 'paid',
  requested_at: '2026-09-28T00:00:00Z',
  paid_at: '2026-10-01T00:00:00Z',
  payout_commissions: [
    {
      commission_id: 'commission-1',
      event_id: 'event-1',
      occurred_at: '2026-09-20T12:00:00Z',
      good_date: '2026-09-20',
      payment_sequence: 1,
      gross_amount: 60,
      withholding_amount: 6,
      net_amount: 54,
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
      withholding_amount: 4,
      net_amount: 36,
      currency: 'USD',
      campaign_id: 'campaign-1',
    },
  ],
  commission_count: 2,
  payout_payment: {
    id: 'payment-1',
    payout_id: 'payout-1',
    amount: 90,
    currency: 'USD',
    payment_method: 'paypal',
    transfer_reference: 'PP-TX-987',
    paid_at: '2026-10-01T00:00:00Z',
    recorded_by_tenant_user_id: 'tenant-user-1',
  },
};

const renderPage = (id = 'payout-1') => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/affiliate/payouts/${id}`]}>
        <Routes>
          <Route path="/affiliate/payouts/:id" element={<PayoutDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
};

describe('PayoutDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows the commission lines and payment reference for a paid payout', async () => {
    vi.mocked(getPayout).mockResolvedValue(paidPayout);
    renderPage();

    expect(await screen.findByText('PP-TX-987')).toBeInTheDocument();
    expect(getPayout).toHaveBeenCalledWith('payout-1');

    // Itemized commission lines reconcile to the totals.
    expect(screen.getByText(/2\s*commissions/)).toBeInTheDocument();
    expect(screen.getAllByText('$60.00').length).toBeGreaterThan(0);
    expect(screen.getAllByText('$40.00').length).toBeGreaterThan(0);
    expect(screen.getAllByText('$90.00').length).toBeGreaterThan(0);
    expect(screen.getByText(/payment method/i)).toBeInTheDocument();
  });

  it('renders a not-found message when the API returns 404', async () => {
    const axiosError = new AxiosError('not found');
    axiosError.response = {
      status: 404,
      statusText: 'Not Found',
      headers: {},
      config: { headers: new AxiosHeaders() },
      data: {},
    };
    vi.mocked(getPayout).mockRejectedValue(axiosError);
    renderPage('someone-elses-payout');

    expect(await screen.findByText(/not found/i)).toBeInTheDocument();
  });

  it('links back to the payout history list', async () => {
    vi.mocked(getPayout).mockResolvedValue(paidPayout);
    renderPage();

    expect(await screen.findByRole('link', { name: /back to payouts/i })).toHaveAttribute(
      'href',
      '/affiliate/payouts'
    );
  });
});
