import { useMemo, useState } from 'react';
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react';
import { ReactNode } from 'react';
import { EmptyState } from './EmptyState';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './Table';
import { TableSkeleton } from './Skeleton';

export interface Column<T> {
  key: string;
  header: ReactNode;
  render: (row: T) => ReactNode;
  sortValue?: (row: T) => string | number;
  className?: string;
  headerClassName?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  rowKey: (row: T) => string;
  isLoading?: boolean;
  emptyTitle: string;
  emptyDescription?: string;
  initialSort?: { key: string; direction: 'asc' | 'desc' };
}

export function DataTable<T>({
  columns,
  data,
  rowKey,
  isLoading,
  emptyTitle,
  emptyDescription,
  initialSort,
}: DataTableProps<T>) {
  const [sort, setSort] = useState<{ key: string; direction: 'asc' | 'desc' } | null>(initialSort ?? null);

  const sorted = useMemo(() => {
    if (!sort) return data;
    const column = columns.find((c) => c.key === sort.key);
    if (!column?.sortValue) return data;
    const values = [...data].sort((a, b) => {
      const av = column.sortValue!(a);
      const bv = column.sortValue!(b);
      if (av < bv) return sort.direction === 'asc' ? -1 : 1;
      if (av > bv) return sort.direction === 'asc' ? 1 : -1;
      return 0;
    });
    return values;
  }, [columns, data, sort]);

  const toggleSort = (key: string) => {
    const column = columns.find((c) => c.key === key);
    if (!column?.sortValue) return;
    setSort((prev) => {
      if (prev?.key !== key) return { key, direction: 'asc' };
      if (prev.direction === 'asc') return { key, direction: 'desc' };
      return null;
    });
  };

  if (isLoading) {
    return <TableSkeleton rows={5} cols={columns.length} />;
  }

  if (data.length === 0) {
    return <EmptyState title={emptyTitle} description={emptyDescription} />;
  }

  return (
    <Table className="w-full table-fixed">
      <TableHead>
        <TableRow>
          {columns.map((col) => (
            <TableHeader key={col.key} className={col.headerClassName}>
              {col.sortValue ? (
                <button
                  type="button"
                  onClick={() => toggleSort(col.key)}
                  className="inline-flex cursor-pointer items-center gap-1 uppercase tracking-wider hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded"
                  aria-label={`Sort by ${typeof col.header === 'string' ? col.header : col.key}`}
                >
                  {col.header}
                  {sort?.key === col.key ? (
                    sort.direction === 'asc' ? (
                      <ArrowUp className="h-3 w-3" aria-hidden="true" />
                    ) : (
                      <ArrowDown className="h-3 w-3" aria-hidden="true" />
                    )
                  ) : (
                    <ArrowUpDown className="h-3 w-3 opacity-50" aria-hidden="true" />
                  )}
                </button>
              ) : (
                col.header
              )}
            </TableHeader>
          ))}
        </TableRow>
      </TableHead>
      <TableBody>
        {sorted.map((row) => (
          <TableRow key={rowKey(row)}>
            {columns.map((col) => (
              <TableCell key={col.key} className={col.className}>
                {col.render(row)}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
