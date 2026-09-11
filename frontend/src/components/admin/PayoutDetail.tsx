import { Payout } from '@/api/types';
import { PayoutStatusBadge } from '@/components/shared/PayoutStatusBadge';
import { formatCurrency } from '@/lib/utils';

export function PayoutDetail({ payout }: { payout: Payout }) {
  return (
    <div className="space-y-2 text-sm text-slate-700">
      <p>
        <span className="font-medium">Status:</span> <PayoutStatusBadge status={payout.status} />
      </p>
      <p>
        <span className="font-medium">Gross:</span> {formatCurrency(payout.approved_amount, payout.currency)}
      </p>
      <p>
        <span className="font-medium">Withholding:</span> {formatCurrency(payout.withholding_total, payout.currency)}
      </p>
      <p>
        <span className="font-medium">Net paid:</span> {formatCurrency(payout.net_paid, payout.currency)}
      </p>
      {payout.paypal_batch_id && (
        <p>
          <span className="font-medium">PayPal batch:</span> {payout.paypal_batch_id}
        </p>
      )}
    </div>
  );
}
