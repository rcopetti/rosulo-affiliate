import { Payout } from '@/api/types';
import { PayoutStatusBadge } from '@/components/shared/PayoutStatusBadge';
import { Button } from '@/components/ui/Button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table';
import { formatCurrency, formatDate, formatDateTime } from '@/lib/utils';

interface PayoutDetailProps {
  payout: Payout;
  /** Called with the payout id when the merchant retries a failed
   * notification email. Omit to hide the action entirely. */
  onRetryNotification?: (id: string) => void;
}

const NOTIFICATION_LABELS: Record<string, string> = {
  pending: 'Email queued',
  sending: 'Email sending',
  sent: 'Email sent',
  failed: 'Email failed',
};

export function PayoutDetail({ payout, onRetryNotification }: PayoutDetailProps) {
  const lines = payout.payout_commissions ?? [];
  const commissionCount = payout.commission_count ?? lines.length;
  const grossTotal = lines.reduce((sum, line) => sum + line.gross_amount, 0);
  const withholdingTotal = lines.reduce((sum, line) => sum + line.withholding_amount, 0);
  const netTotal = lines.reduce((sum, line) => sum + line.net_amount, 0);

  return (
    <div className="space-y-4 text-sm text-slate-700">
      <p className="flex items-center justify-between">
        <span className="font-medium">Status</span>
        <PayoutStatusBadge status={payout.status} />
      </p>

      {payout.affiliate && (
        <div className="space-y-1 rounded-md bg-surface-muted p-3">
          <p>
            <span className="font-medium">Affiliate:</span> {payout.affiliate.name}
          </p>
          <p>
            <span className="font-medium">Email:</span> {payout.affiliate.email}
          </p>
          <p>
            <span className="font-medium">PayPal email:</span>{' '}
            {payout.affiliate.paypal_email ?? '—'}
          </p>
        </div>
      )}

      <div className="grid grid-cols-3 gap-2">
        <div className="rounded-md bg-surface-muted p-3">
          <p className="text-xs text-fg-muted">Gross</p>
          <p className="font-medium">{formatCurrency(payout.approved_amount, payout.currency)}</p>
        </div>
        <div className="rounded-md bg-surface-muted p-3">
          <p className="text-xs text-fg-muted">Withholding</p>
          <p className="font-medium">{formatCurrency(payout.withholding_total, payout.currency)}</p>
        </div>
        <div className="rounded-md bg-surface-muted p-3">
          <p className="text-xs text-fg-muted">Net payout</p>
          <p className="font-medium">{formatCurrency(payout.net_paid, payout.currency)}</p>
        </div>
      </div>

      <div>
        <p className="mb-2 font-medium">
          {commissionCount} {commissionCount === 1 ? 'commission' : 'commissions'}
          {payout.earliest_sale_at && payout.latest_sale_at && (
            <span className="ml-1 font-normal text-fg-muted">
              · sales from {formatDate(payout.earliest_sale_at)} to{' '}
              {formatDate(payout.latest_sale_at)}
            </span>
          )}
        </p>
        <Table>
          <TableHead>
            <TableRow>
              <TableHeader>Sale date</TableHeader>
              <TableHeader>Good date</TableHeader>
              <TableHeader>Seq</TableHeader>
              <TableHeader className="text-right">Gross</TableHeader>
              <TableHeader className="text-right">Withholding</TableHeader>
              <TableHeader className="text-right">Net</TableHeader>
            </TableRow>
          </TableHead>
          <TableBody>
            {lines.map((line) => (
              <TableRow key={line.commission_id}>
                <TableCell className="whitespace-nowrap">
                  {line.occurred_at ? formatDateTime(line.occurred_at) : '—'}
                </TableCell>
                <TableCell className="whitespace-nowrap">
                  {line.good_date ? formatDate(line.good_date) : '—'}
                </TableCell>
                <TableCell>{line.payment_sequence ?? '—'}</TableCell>
                <TableCell className="text-right whitespace-nowrap">
                  {formatCurrency(line.gross_amount, line.currency)}
                </TableCell>
                <TableCell className="text-right whitespace-nowrap">
                  {formatCurrency(line.withholding_amount, line.currency)}
                </TableCell>
                <TableCell className="text-right whitespace-nowrap">
                  {formatCurrency(line.net_amount, line.currency)}
                </TableCell>
              </TableRow>
            ))}
            {lines.length > 0 && (
              <TableRow>
                <td colSpan={3} className="px-4 py-3 text-sm font-medium text-fg">
                  Total
                </td>
                <TableCell className="text-right whitespace-nowrap font-medium">
                  {formatCurrency(grossTotal, payout.currency)}
                </TableCell>
                <TableCell className="text-right whitespace-nowrap font-medium">
                  {formatCurrency(withholdingTotal, payout.currency)}
                </TableCell>
                <TableCell className="text-right whitespace-nowrap font-medium">
                  {formatCurrency(netTotal, payout.currency)}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {payout.payout_notification && (
        <p className="flex items-center justify-between">
          <span className="font-medium">Affiliate notification</span>
          <span className="flex items-center gap-2">
            <span>{NOTIFICATION_LABELS[payout.payout_notification.status] ?? payout.payout_notification.status}</span>
            {payout.payout_notification.status === 'failed' && onRetryNotification && (
              <Button
                size="sm"
                variant="secondary"
                onClick={() => onRetryNotification(payout.id)}
              >
                Retry email
              </Button>
            )}
          </span>
        </p>
      )}

      {payout.payout_payment && (
        <div className="space-y-1 rounded-md bg-surface-muted p-3">
          <p>
            <span className="font-medium">Payment method:</span>{' '}
            {payout.payout_payment.payment_method}
          </p>
          <p>
            <span className="font-medium">Transfer reference:</span>{' '}
            {payout.payout_payment.transfer_reference}
          </p>
          <p>
            <span className="font-medium">Paid at:</span>{' '}
            {formatDateTime(payout.payout_payment.paid_at)}
          </p>
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
