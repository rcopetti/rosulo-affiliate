import { formatCurrency } from '@/lib/utils';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table';

interface Row {
  period: string;
  gross: number;
  tax_retained: number;
}

export function CommissionLiability({ data, currency = 'USD' }: { data: Row[]; currency?: string }) {
  return (
    <Table>
      <TableHead>
        <TableRow>
          <TableHeader>Period</TableHeader>
          <TableHeader>Gross</TableHeader>
          <TableHeader>Tax retained</TableHeader>
        </TableRow>
      </TableHead>
      <TableBody>
        {data.map((r) => (
          <TableRow key={r.period}>
            <TableCell>{r.period}</TableCell>
            <TableCell>{formatCurrency(r.gross, currency)}</TableCell>
            <TableCell>{formatCurrency(r.tax_retained, currency)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
