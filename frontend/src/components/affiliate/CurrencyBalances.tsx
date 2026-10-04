import type { Balance, CurrencyBalance } from '@/api/types';
import { BalanceSummary } from '@/components/affiliate/BalanceSummary';
import { StatsCards } from '@/components/affiliate/StatsCards';

export function CurrencyBalances({ balance }: { balance: Balance }) {
  const currencies = balance.balances_by_currency.length
    ? balance.balances_by_currency
    : [
        {
          currency: balance.currency ?? 'USD',
          earned: balance.earned ?? 0,
          pending: balance.pending ?? 0,
          available: balance.available ?? 0,
          paid: balance.paid ?? 0,
          reserved: balance.reserved ?? 0,
          tax_retained: balance.tax_retained ?? 0,
          reversal_total: balance.reversal_total ?? 0,
        },
      ];

  return (
    <div className="space-y-6">
      {currencies.map((currencyBalance: CurrencyBalance) => (
        <section
          key={currencyBalance.currency}
          className="space-y-4"
          aria-labelledby={`balance-${currencyBalance.currency}`}
        >
          <h2 id={`balance-${currencyBalance.currency}`} className="text-lg font-semibold">
            {currencyBalance.currency} balance
          </h2>
          <StatsCards
            earned={currencyBalance.earned}
            pending={currencyBalance.pending}
            available={currencyBalance.available}
            reserved={currencyBalance.reserved}
            paid={currencyBalance.paid}
            currency={currencyBalance.currency}
          />
          <BalanceSummary balance={currencyBalance} />
        </section>
      ))}
    </div>
  );
}
