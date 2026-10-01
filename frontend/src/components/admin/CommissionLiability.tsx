import { formatCurrency } from '@/lib/utils';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table';

interface Row {
  period: string;
  currency: string;
  gross: number;
  tax_retained: number;
}

export function CommissionLiability({ data }: { data: Row[] }) {
  return (
    <Table>
      <TableHead>
        <TableRow>
          <TableHeader>Period</TableHeader>
          <TableHeader>Currency</TableHeader>
          <TableHeader>Gross</TableHeader>
          <TableHeader>Tax retained</TableHeader>
        </TableRow>
      </TableHead>
      <TableBody>
        {data.map((r) => (
          <TableRow key={`${r.period}-${r.currency}`}>
            <TableCell>{r.period}</TableCell>
            <TableCell>{r.currency}</TableCell>
            <TableCell>{formatCurrency(r.gross, r.currency)}</TableCell>
            <TableCell>{formatCurrency(r.tax_retained, r.currency)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
