import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { CurrencyBalances } from '@/components/affiliate/CurrencyBalances';
import type { Balance } from '@/api/types';

const balance: Balance = {
  balances_by_currency: [
    {
      currency: 'USD', earned: 10, pending: 1, available: 2, paid: 7,
      tax_retained: 0, reversal_total: 0,
    },
    {
      currency: 'EUR', earned: 20, pending: 3, available: 4, paid: 13,
      tax_retained: 0, reversal_total: 0,
    },
  ],
  earned: null,
  pending: null,
  available: null,
  paid: null,
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
});
