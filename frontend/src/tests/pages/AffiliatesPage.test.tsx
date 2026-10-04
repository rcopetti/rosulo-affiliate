import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { getAffiliateInvites, getAffiliates } from '@/api/admin/affiliates';
import { AffiliatesPage } from '@/pages/admin/AffiliatesPage';

vi.mock('@/api/admin/affiliates', async (importActual) => {
  const actual = await importActual<typeof import('@/api/admin/affiliates')>();
  return { ...actual, getAffiliates: vi.fn(), getAffiliateInvites: vi.fn() };
});

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AffiliatesPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('AffiliatesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getAffiliates).mockResolvedValue([]);
    vi.mocked(getAffiliateInvites).mockResolvedValue([]);
  });

  it('shows pending invitations awaiting a response', async () => {
    vi.mocked(getAffiliateInvites).mockResolvedValue([
      {
        id: 'inv-1',
        email: 'pending@example.com',
        status: 'pending',
        expires_at: new Date(Date.now() + 86_400_000).toISOString(),
        created_at: '2026-10-01T12:00:00Z',
      },
    ]);

    renderPage();

    expect(await screen.findByText('Pending invitations')).toBeInTheDocument();
    expect(await screen.findByText('pending@example.com')).toBeInTheDocument();
    expect(screen.getByText('Pending')).toBeInTheDocument();
  });

  it('marks an invite past its expiry as expired', async () => {
    vi.mocked(getAffiliateInvites).mockResolvedValue([
      {
        id: 'inv-2',
        email: 'stale@example.com',
        status: 'pending',
        expires_at: '2020-01-01T00:00:00Z',
        created_at: '2019-12-25T00:00:00Z',
      },
    ]);

    renderPage();

    expect(await screen.findByText('stale@example.com')).toBeInTheDocument();
    expect(screen.getByText('Expired')).toBeInTheDocument();
  });

  it('shows an empty state when no invitations are pending', async () => {
    renderPage();

    expect(
      await screen.findByText('No invitations awaiting a response.')
    ).toBeInTheDocument();
  });
});
