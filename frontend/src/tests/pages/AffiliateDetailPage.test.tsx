import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { getAffiliate } from '@/api/admin/affiliates';
import { getContract } from '@/api/admin/contracts';
import { AffiliateDetailPage } from '@/pages/admin/AffiliateDetailPage';
import { ToastProvider } from '@/components/ui/Toast';

vi.mock('@/api/admin/affiliates', () => ({
  getAffiliate: vi.fn(),
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
  });

  it('shows the tenant-scoped decision and rejection reason', async () => {
    renderPage();

    expect(await screen.findByText('Tax form rejected')).toBeInTheDocument();
    expect(screen.getAllByText(/The form is unsigned/).length).toBeGreaterThan(0);
    expect(screen.getByLabelText(/rejection reason/i)).toBeInTheDocument();
  });
});
