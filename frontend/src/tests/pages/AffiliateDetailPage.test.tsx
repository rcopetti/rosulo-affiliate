import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { getAffiliate, getAffiliatePayouts } from '@/api/admin/affiliates';
import { getContract } from '@/api/admin/contracts';
import { AffiliateDetailPage } from '@/pages/admin/AffiliateDetailPage';
import { ToastProvider } from '@/components/ui/Toast';

vi.mock('@/api/admin/affiliates', () => ({
  getAffiliate: vi.fn(),
  getAffiliatePayouts: vi.fn(),
  reviewAffiliateDocument: vi.fn(),
  viewAffiliateDocument: vi.fn(),
}));
vi.mock('@/api/admin/contracts', () => ({ getContract: vi.fn() }));

const renderPage = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter
        initialEntries={['/admin/affiliates/affiliate-1']}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <ToastProvider>
          <Routes>
            <Route path="/admin/affiliates/:id" element={<AffiliateDetailPage />} />
          </Routes>
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
};

const payoutHistory = {
  items: [
    {
      id: 'payout-2',
      status: 'paid',
      currency: 'EUR',
      requested_amount: 7.5,
      approved_amount: 7.5,
      withholding_total: 0,
      net_paid: 7.5,
      requested_at: '2026-09-20T12:00:00Z',
      approved_at: '2026-09-21T12:00:00Z',
      paid_at: '2026-09-22T12:00:00Z',
      payment_reference: 'PP-TX-EUR',
    },
    {
      id: 'payout-1',
      status: 'pending_approval',
      currency: 'USD',
      requested_amount: 10,
      approved_amount: 10,
      withholding_total: 0,
      net_paid: 10,
      requested_at: '2026-09-10T12:00:00Z',
      approved_at: null,
      paid_at: null,
      payment_reference: null,
    },
  ],
  total: 2,
  limit: 20,
  offset: 0,
  paid_totals_by_currency: [
    { currency: 'USD', rolling_12_months: 30, year_to_date: 10 },
    { currency: 'EUR', rolling_12_months: 7.5, year_to_date: 7.5 },
  ],
};

describe('AffiliateDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getAffiliate).mockResolvedValue({
      id: 'affiliate-1',
      tenant_id: 'tenant-1',
      account_id: 'account-1',
      name: 'Affiliate One',
      email: 'affiliate@example.com',
      documents: [{
        id: 'document-1',
        document_type: 'W-9',
        content_type: 'application/pdf',
        created_at: '2026-10-01T00:00:00Z',
        status: 'rejected',
        review_history: [{
          status: 'rejected',
          reviewed_at: '2026-10-01T00:00:00Z',
          rejection_reason: 'The form is unsigned',
          reviewer: { id: 'reviewer-1', name: 'Merchant Reviewer', email: 'reviewer@example.com' },
        }],
      }],
      payout_eligibility: {
        eligible: false,
        status: 'rejected',
        reason: 'The form is unsigned',
      },
      enabled: true,
    } as never);
    vi.mocked(getContract).mockResolvedValue({ terms: [] } as never);
    vi.mocked(getAffiliatePayouts).mockResolvedValue(payoutHistory as never);
  });

  it('shows the tenant-scoped decision and rejection reason', async () => {
    renderPage();

    expect(await screen.findByText('Tax form rejected')).toBeInTheDocument();
    expect(screen.getAllByText(/The form is unsigned/).length).toBeGreaterThan(0);
    expect(screen.getByLabelText(/rejection reason/i)).toBeInTheDocument();
  });

  it('shows per-currency paid totals and the payout history', async () => {
    renderPage();

    expect(await screen.findByText('Payout history')).toBeInTheDocument();

    // Per-currency paid totals are never summed across currencies.
    expect(screen.getByText('Paid last 12 months')).toBeInTheDocument();
    expect(screen.getByText('Paid year to date')).toBeInTheDocument();
    expect(screen.getByText('$30.00')).toBeInTheDocument();
    expect(screen.getAllByText('$10.00').length).toBeGreaterThan(0);
    expect(screen.getAllByText('€7.50').length).toBeGreaterThan(0);
    expect(screen.queryByText(/earned commissions/i)).not.toBeInTheDocument();

    // History rows show status, gross/net, and the payment reference.
    expect(screen.getByText('paid')).toBeInTheDocument();
    expect(screen.getByText('pending approval')).toBeInTheDocument();
    expect(screen.getByText('PP-TX-EUR')).toBeInTheDocument();
  });

  it('requests the next payout page when paginating', async () => {
    vi.mocked(getAffiliatePayouts).mockResolvedValue({
      ...payoutHistory,
      total: 25,
    } as never);
    renderPage();

    expect(await screen.findByText('Payout history')).toBeInTheDocument();
    const next = await screen.findByRole('button', { name: 'Next' });
    fireEvent.click(next);

    expect(vi.mocked(getAffiliatePayouts)).toHaveBeenLastCalledWith(
      'affiliate-1',
      { limit: 20, offset: 20 },
    );
  });
});
