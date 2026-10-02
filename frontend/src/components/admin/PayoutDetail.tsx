import { Payout } from '@/api/types';
import { PayoutStatusBadge } from '@/components/shared/PayoutStatusBadge';
import { formatCurrency, formatDateTime } from '@/lib/utils';

export function PayoutDetail({ payout }: { payout: Payout }) {
  return (
    <div className="space-y-3 text-sm text-slate-700">
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
        <span className="font-medium">Net:</span> {formatCurrency(payout.net_paid, payout.currency)}
      </p>
      {payout.payment_record && (
        <div className="space-y-1 rounded-md bg-surface-muted p-3">
          <p><span className="font-medium">Payment method:</span> {payout.payment_record.payment_method}</p>
          <p><span className="font-medium">Transfer reference:</span> {payout.payment_record.transfer_reference}</p>
          <p><span className="font-medium">Recorded:</span> {formatDateTime(payout.payment_record.paid_at)}</p>
        </div>
      )}
      {!!payout.transitions?.length && (
        <ol aria-label="Payout history" className="space-y-1">
          {payout.transitions.map((transition) => (
            <li key={transition.id}>
              {transition.to_status.replace('_', ' ')} · {formatDateTime(transition.created_at)}
              {transition.actor_tenant_user_id ? ' · merchant user' : ' · system'}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
