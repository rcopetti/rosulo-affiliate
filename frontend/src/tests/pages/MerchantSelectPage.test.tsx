import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fetchMerchants, selectMerchant } from '@/api/auth';
import { MerchantSelectPage } from '@/pages/affiliate/MerchantSelectPage';
import type { LinkedMerchant } from '@/api/types';

vi.mock('@/api/auth', async (importActual) => {
  const actual = await importActual<typeof import('@/api/auth')>();
  return { ...actual, fetchMerchants: vi.fn(), selectMerchant: vi.fn() };
});

const setTenant = vi.fn();
vi.mock('@/store/auth', () => ({
  useAuthStore: (selector: (state: { setTenant: typeof setTenant }) => unknown) =>
    selector({ setTenant }),
}));

vi.mock('@/components/ui/Toast', () => ({ useToast: () => ({ add: vi.fn() }) }));

const merchants: LinkedMerchant[] = [
  { tenant_id: 'tenant-a', name: 'Acme' },
  { tenant_id: 'tenant-b', name: 'Globex' },
];

function renderPage(entry = '/merchants') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/merchants" element={<MerchantSelectPage />} />
          <Route path="/affiliate/payouts/:id" element={<p>PAYOUT DETAIL</p>} />
          <Route path="/affiliate/dashboard" element={<p>DASHBOARD</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('MerchantSelectPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(fetchMerchants).mockResolvedValue(merchants);
    vi.mocked(selectMerchant).mockResolvedValue(undefined);
  });

  it('selects a merchant by tenant_id and lands on the dashboard', async () => {
    renderPage();

    fireEvent.click(await screen.findByText('Acme'));

    await waitFor(() => expect(selectMerchant).toHaveBeenCalledWith('tenant-a'));
    expect(setTenant).toHaveBeenCalledWith('tenant-a');
    expect(await screen.findByText('DASHBOARD')).toBeInTheDocument();
  });

  it('continues to a preserved payout deep link for the selected tenant', async () => {
    renderPage(
      '/merchants?returnTo=' +
        encodeURIComponent('/affiliate/payouts/payout-1?tenant_id=tenant-b')
    );

    fireEvent.click(await screen.findByText('Globex'));

    expect(selectMerchant).toHaveBeenCalledWith('tenant-b');
    expect(await screen.findByText('PAYOUT DETAIL')).toBeInTheDocument();
  });

  it('ignores a deep link that targets a different merchant', async () => {
    renderPage(
      '/merchants?returnTo=' +
        encodeURIComponent('/affiliate/payouts/payout-1?tenant_id=tenant-b')
    );

    fireEvent.click(await screen.findByText('Acme'));

    expect(selectMerchant).toHaveBeenCalledWith('tenant-a');
    expect(await screen.findByText('DASHBOARD')).toBeInTheDocument();
  });
});
