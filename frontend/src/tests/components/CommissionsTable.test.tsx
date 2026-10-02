import { render, screen } from '@testing-library/react';
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
  available_on: '2026-10-01',
  available_at: '2026-10-01T00:00:00Z',
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
});
