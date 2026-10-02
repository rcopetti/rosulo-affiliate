import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { getBalance } from '@/api/affiliate/balance';
import { getCommissions } from '@/api/affiliate/commissions';
import { getAffiliateDocuments } from '@/api/affiliate/profile';
import { requestPayout } from '@/api/affiliate/payouts';
import { RequestPayoutPage } from '@/pages/affiliate/RequestPayoutPage';
import { ToastProvider } from '@/components/ui/Toast';
import type { AffiliateDocumentStatus, Commission } from '@/api/types';

vi.mock('@/api/affiliate/balance', () => ({ getBalance: vi.fn() }));
vi.mock('@/api/affiliate/commissions', () => ({ getCommissions: vi.fn() }));
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

const eligibleDocuments: AffiliateDocumentStatus = {
  required_document_type: 'W-9',
  documents: [{
    id: 'doc-1',
    document_type: 'W-9',
    content_type: 'application/pdf',
    created_at: '2026-10-01T00:00:00Z',
    status: 'approved',
    review_history: [],
  }],
  payout_eligibility: {
    eligible: true,
    status: 'approved',
    reason: null,
  },
};

const rejectedDocuments: AffiliateDocumentStatus = {
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
};

const commission = (overrides: Partial<Commission>): Commission => ({
  id: 'commission-1',
  event_id: 'evt-1',
  gross_amount: 10,
  withholding_amount: 1,
  net_amount: 9,
  currency: 'USD',
  status: 'available',
  available_on: '2026-10-01',
  available_at: '2026-10-01T00:00:00Z',
  ...overrides,
});

const commissions: Commission[] = [
  commission({ id: 'commission-usd-1', event_id: 'evt-usd-1', gross_amount: 10, withholding_amount: 1, net_amount: 9 }),
  commission({ id: 'commission-usd-2', event_id: 'evt-usd-2', gross_amount: 20, withholding_amount: 2, net_amount: 18 }),
  commission({ id: 'commission-pending', event_id: 'evt-pending', status: 'pending', available_at: null }),
  commission({ id: 'commission-reserved', event_id: 'evt-reserved', status: 'reserved' }),
  commission({ id: 'commission-paid', event_id: 'evt-paid', status: 'paid' }),
  commission({ id: 'commission-reversed', event_id: 'evt-reversed', status: 'reversed' }),
  commission({ id: 'commission-eur', event_id: 'evt-eur', currency: 'EUR' }),
];

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
        currency: 'USD', earned: 30, pending: 0, available: 27, paid: 0, reserved: 9,
        tax_retained: 3, reversal_total: 0,
      }],
      earned: 30,
      pending: 0,
      available: 27,
      paid: 0,
      reserved: 9,
      reversed: 0,
      tax_retained: 3,
      reversal_total: 0,
      debt: 0,
      currency: 'USD',
    });
    vi.mocked(getCommissions).mockResolvedValue(commissions);
    vi.mocked(getAffiliateDocuments).mockResolvedValue(rejectedDocuments);
  });

  it('shows the backend rejection reason and blocks the payout request', async () => {
    renderPage();

    expect(await screen.findByText('The form is unsigned')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Payout currency'), { target: { value: 'USD' } });
    expect(screen.getByRole('button', { name: /request payout/i })).toBeDisabled();
    expect(getAffiliateDocuments).toHaveBeenCalled();
  });

  it('requests a payout for only the selected whole commissions', async () => {
    vi.mocked(getAffiliateDocuments).mockResolvedValue(eligibleDocuments);
    vi.mocked(requestPayout).mockResolvedValue({} as never);
    renderPage();

    fireEvent.change(await screen.findByLabelText('Payout currency'), { target: { value: 'USD' } });
    fireEvent.click(await screen.findByLabelText('Selected commissions'));
    fireEvent.click(await screen.findByLabelText('Select commission evt-usd-2'));

    expect(screen.getByText('1 commission')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /request payout of \$18\.00/i }));

    await waitFor(() => {
      expect(requestPayout).toHaveBeenCalledWith({
        currency: 'USD',
        commission_ids: ['commission-usd-2'],
      });
    });
  });

  it('requests a payout for all available commissions without commission_ids', async () => {
    vi.mocked(getAffiliateDocuments).mockResolvedValue(eligibleDocuments);
    vi.mocked(requestPayout).mockResolvedValue({} as never);
    renderPage();

    fireEvent.change(await screen.findByLabelText('Payout currency'), { target: { value: 'USD' } });
    expect(await screen.findByText('2 commissions')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /request payout of \$27\.00/i }));

    await waitFor(() => {
      expect(requestPayout).toHaveBeenCalledWith({ currency: 'USD' });
    });
  });

  it('only offers available commissions for selection and renders no amount input', async () => {
    vi.mocked(getAffiliateDocuments).mockResolvedValue(eligibleDocuments);
    renderPage();

    fireEvent.change(await screen.findByLabelText('Payout currency'), { target: { value: 'USD' } });
    fireEvent.click(await screen.findByLabelText('Selected commissions'));

    expect(await screen.findByLabelText('Select commission evt-usd-1')).toBeInTheDocument();
    expect(screen.getByLabelText('Select commission evt-usd-2')).toBeInTheDocument();
    expect(screen.queryByLabelText('Select commission evt-pending')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Select commission evt-reserved')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Select commission evt-paid')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Select commission evt-reversed')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Select commission evt-eur')).not.toBeInTheDocument();
    expect(screen.queryByRole('spinbutton')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /request payout/i })).toBeDisabled();
  });
});
