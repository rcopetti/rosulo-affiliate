import { useQuery } from '@tanstack/react-query';
import { AxiosError } from 'axios';
import { Link, useParams } from 'react-router-dom';
import { getPayout } from '@/api/affiliate/payouts';
import { PayoutStatusBadge } from '@/components/shared/PayoutStatusBadge';
import { Card } from '@/components/ui/Card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table';
import { formatCurrency, formatDate, formatDateTime } from '@/lib/utils';

/**
 * Affiliate-facing payout detail — the landing page for the payout-paid
 * email deep link. The API enforces affiliate + tenant ownership; the
 * `tenant_id` query param in the emailed URL only drove the post-login
 * tenant selection, it grants nothing by itself.
 */
export function PayoutDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: payout, isLoading, error } = useQuery({
    queryKey: ['affiliate-payout', id],
    queryFn: () => getPayout(id as string),
    enabled: !!id,
    retry: false,
  });

  const lines = payout?.payout_commissions ?? [];
  const grossTotal = lines.reduce((sum, line) => sum + line.gross_amount, 0);
  const withholdingTotal = lines.reduce((sum, line) => sum + line.withholding_amount, 0);
  const netTotal = lines.reduce((sum, line) => sum + line.net_amount, 0);

  const notFound = (error as AxiosError | null)?.response?.status === 404;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Payout detail</h1>
        <Link to="/affiliate/payouts" className="text-sm text-brand-600 hover:underline">
          Back to payouts
        </Link>
      </div>
      <Card>
        {isLoading ? (
          <p className="text-sm text-fg-muted">Loading…</p>
        ) : notFound ? (
          <p className="text-sm text-fg-muted">This payout was not found.</p>
        ) : error || !payout ? (
          <p className="text-sm text-fg-muted">Could not load this payout.</p>
        ) : (
          <div className="space-y-4 text-sm text-slate-700">
            <p className="flex items-center justify-between">
              <span className="font-medium">Status</span>
              <PayoutStatusBadge status={payout.status} />
            </p>
            <p>
              <span className="font-medium">Requested:</span> {formatDateTime(payout.requested_at)}
            </p>

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
                {payout.commission_count ?? lines.length}{' '}
                {(payout.commission_count ?? lines.length) === 1 ? 'commission' : 'commissions'}
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

            {payout.payout_payment && (
              <div className="space-y-1 rounded-md bg-surface-muted p-3">
                <p>
                  <span className="font-medium">Payment method:</span>{' '}
                  <span className="capitalize">
                    {payout.payout_payment.payment_method.replace(/_/g, ' ')}
                  </span>
                </p>
                <p>
                  <span className="font-medium">Transfer reference:</span>{' '}
                  <span className="font-mono">{payout.payout_payment.transfer_reference}</span>
                </p>
                <p>
                  <span className="font-medium">Paid at:</span>{' '}
                  {formatDateTime(payout.payout_payment.paid_at)}
                </p>
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
