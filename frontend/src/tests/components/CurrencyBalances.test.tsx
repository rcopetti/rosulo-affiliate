import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { CurrencyBalances } from '@/components/affiliate/CurrencyBalances';
import type { Balance } from '@/api/types';

const balance: Balance = {
  balances_by_currency: [
    {
      currency: 'USD', earned: 10, pending: 1, available: 2, paid: 8, reserved: 5,
      tax_retained: 0, reversal_total: 0,
    },
    {
      currency: 'EUR', earned: 20, pending: 3, available: 4, paid: 13, reserved: 6,
      tax_retained: 0, reversal_total: 0,
    },
  ],
  earned: null,
  pending: null,
  available: null,
  paid: null,
  reserved: null,
  reversed: null,
  tax_retained: null,
  reversal_total: null,
  debt: null,
  currency: null,
};

describe('CurrencyBalances', () => {
  it('renders balances separately without creating a combined total', () => {
    render(<CurrencyBalances balance={balance} />);
    expect(screen.getByRole('heading', { name: 'USD balance' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'EUR balance' })).toBeInTheDocument();
    expect(screen.getByText('$10.00')).toBeInTheDocument();
    expect(screen.getByText('€20.00')).toBeInTheDocument();
    expect(screen.queryByText('$30.00')).not.toBeInTheDocument();
  });

  it('shows the reserved bucket per currency without adding it to available', () => {
    render(<CurrencyBalances balance={balance} />);
    expect(screen.getAllByText('Reserved')).toHaveLength(2);
    expect(screen.getByText('$5.00')).toBeInTheDocument();
    expect(screen.getByText('€6.00')).toBeInTheDocument();
    // available is reported on its own: USD available stays $2.00, not $7.00
    expect(screen.getByText('$2.00')).toBeInTheDocument();
    expect(screen.queryByText('$7.00')).not.toBeInTheDocument();
  });

  it('falls back to the legacy flat balance fields including reserved', () => {
    const legacy: Balance = {
      balances_by_currency: [],
      earned: 10,
      pending: 1,
      available: 2,
      paid: 7,
      reserved: 4,
      reversed: 0,
      tax_retained: 0,
      reversal_total: 0,
      debt: 0,
      currency: 'USD',
    };
    render(<CurrencyBalances balance={legacy} />);
    expect(screen.getByText('Reserved')).toBeInTheDocument();
    expect(screen.getByText('$4.00')).toBeInTheDocument();
  });
});
