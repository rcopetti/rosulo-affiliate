import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { getBalance } from '@/api/affiliate/balance';
import { getAffiliateDocuments } from '@/api/affiliate/profile';
import { RequestPayoutPage } from '@/pages/affiliate/RequestPayoutPage';
import { ToastProvider } from '@/components/ui/Toast';

vi.mock('@/api/affiliate/balance', () => ({ getBalance: vi.fn() }));
vi.mock('@/api/affiliate/profile', () => ({
  getAffiliateDocuments: vi.fn(),
}));
vi.mock('@/api/affiliate/payouts', () => ({ requestPayout: vi.fn() }));
vi.mock('@/components/ui/Select', () => ({
  Select: ({
    label,
    value,
    onChange,
    options,
  }: {
    label: string;
    value: string;
    onChange: (value: string) => void;
    options: { value: string; label: string }[];
  }) => (
    <label>
      {label}
      <select aria-label={label} value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Choose a currency</option>
        {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
    </label>
  ),
}));

const renderPage = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ToastProvider>
          <RequestPayoutPage />
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
};

describe('RequestPayoutPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getBalance).mockResolvedValue({
      balances_by_currency: [{
        currency: 'USD', earned: 10, pending: 0, available: 10, paid: 0,
        tax_retained: 0, reversal_total: 0,
      }],
      earned: 10,
      pending: 0,
      available: 10,
      paid: 0,
      reversed: 0,
      tax_retained: 0,
      reversal_total: 0,
      debt: 0,
      currency: 'USD',
    });
    vi.mocked(getAffiliateDocuments).mockResolvedValue({
      required_document_type: 'W-9',
      documents: [{
        id: 'doc-1',
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
    });
  });

  it('shows the backend rejection reason and blocks the payout request', async () => {
    renderPage();

    expect(await screen.findByText('The form is unsigned')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Payout currency'), { target: { value: 'USD' } });
    expect(screen.getByRole('button', { name: /request payout of/i })).toBeDisabled();
    expect(getAffiliateDocuments).toHaveBeenCalled();
  });
});
