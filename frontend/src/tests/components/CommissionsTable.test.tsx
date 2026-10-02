import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Commission } from '@/api/types';
import { CommissionsTable } from '@/components/affiliate/CommissionsTable';

const commission = (overrides: Partial<Commission>): Commission => ({
  id: 'commission-1',
  event_id: 'evt-1',
  gross_amount: 100,
  withholding_amount: 10,
  net_amount: 90,
  currency: 'USD',
  status: 'available',
  available_at: '2026-10-01T00:00:00Z',
  created_at: '2026-10-01T00:00:00Z',
  ...overrides,
});

describe('CommissionsTable', () => {
  it('renders gross, withholding and net amounts for each commission', () => {
    render(<CommissionsTable commissions={[commission({})]} />);

    expect(screen.getByText('evt-1')).toBeInTheDocument();
    expect(screen.getByText('$100.00')).toBeInTheDocument();
    expect(screen.getByText('$10.00')).toBeInTheDocument();
    expect(screen.getByText('$90.00')).toBeInTheDocument();
    expect(screen.getByText('available')).toBeInTheDocument();
  });

  it('renders the reserved status badge for reserved commissions', () => {
    render(<CommissionsTable commissions={[commission({ status: 'reserved' })]} />);

    expect(screen.getByText('reserved')).toHaveClass('bg-info-soft', 'text-info-fg');
  });

  it('filters commissions by status', () => {
    render(
      <CommissionsTable
        commissions={[
          commission({ id: 'c-avail', event_id: 'evt-avail', status: 'available' }),
          commission({ id: 'c-paid', event_id: 'evt-paid', status: 'paid' }),
        ]}
      />
    );

    fireEvent.change(screen.getByLabelText('Filter by status'), {
      target: { value: 'paid' },
    });

    expect(screen.queryByText('evt-avail')).not.toBeInTheDocument();
    expect(screen.getByText('evt-paid')).toBeInTheDocument();
  });

  it('filters commissions by the today period', () => {
    const today = new Date().toISOString();
    render(
      <CommissionsTable
        commissions={[
          commission({ id: 'c-new', event_id: 'evt-new', created_at: today }),
          commission({ id: 'c-old', event_id: 'evt-old', created_at: '2020-01-01T00:00:00Z' }),
        ]}
      />
    );

    fireEvent.change(screen.getByLabelText('Filter by period'), {
      target: { value: 'today' },
    });

    expect(screen.getByText('evt-new')).toBeInTheDocument();
    expect(screen.queryByText('evt-old')).not.toBeInTheDocument();
  });

  it('filters commissions by a custom date range', () => {
    render(
      <CommissionsTable
        commissions={[
          commission({ id: 'c-in', event_id: 'evt-in', created_at: '2026-09-15T12:00:00Z' }),
          commission({ id: 'c-out', event_id: 'evt-out', created_at: '2026-10-05T12:00:00Z' }),
        ]}
      />
    );

    fireEvent.change(screen.getByLabelText('Filter by period'), {
      target: { value: 'custom' },
    });
    fireEvent.change(screen.getByLabelText('From date'), {
      target: { value: '2026-09-01' },
    });
    fireEvent.change(screen.getByLabelText('To date'), {
      target: { value: '2026-09-30' },
    });

    expect(screen.getByText('evt-in')).toBeInTheDocument();
    expect(screen.queryByText('evt-out')).not.toBeInTheDocument();
  });

  it('paginates commissions with Previous and Next', () => {
    const rows = Array.from({ length: 12 }, (_, i) =>
      commission({
        id: `c-${i}`,
        event_id: `evt-${i}`,
        created_at: `2026-10-${String(i + 1).padStart(2, '0')}T00:00:00Z`,
      })
    );
    render(<CommissionsTable commissions={rows} />);

    expect(screen.getByText('Page 1 of 2')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getByText('Page 2 of 2')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Previous' }));
    expect(screen.getByText('Page 1 of 2')).toBeInTheDocument();
  });
});
