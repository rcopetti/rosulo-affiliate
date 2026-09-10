import { cn } from '@/lib/utils';
import { ReactNode } from 'react';

export function Table({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className="overflow-x-auto">
      <table className={cn('min-w-full divide-y divide-slate-200', className)}>{children}</table>
    </div>
  );
}

export function TableHead({ children }: { children: ReactNode }) {
  return (
    <thead className="bg-slate-50">
      <tr>{children}</tr>
    </thead>
  );
}

export function TableBody({ children }: { children: ReactNode }) {
  return <tbody className="divide-y divide-slate-200 bg-white">{children}</tbody>;
}

export function TableRow({ children, className }: { children: ReactNode; className?: string }) {
  return <tr className={cn('hover:bg-slate-50', className)}>{children}</tr>;
}

export function TableHeader({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <th
      scope="col"
      className={cn('px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500', className)}
    >
      {children}
    </th>
  );
}

export function TableCell({ children, className }: { children: ReactNode; className?: string }) {
  return <td className={cn('px-4 py-3 text-sm text-slate-700', className)}>{children}</td>;
}
