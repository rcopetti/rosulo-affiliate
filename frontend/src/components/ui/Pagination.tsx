import { Button } from './Button';

interface PaginationProps {
  skip: number;
  limit: number;
  total: number;
  onSkipChange: (skip: number) => void;
  onLimitChange: (limit: number) => void;
}

export function Pagination({ skip, limit, total, onSkipChange, onLimitChange }: PaginationProps) {
  const hasPrev = skip > 0;
  const hasNext = skip + limit < total;
  const currentPage = Math.floor(skip / limit) + 1;
  const totalPages = Math.max(Math.ceil(total / limit), 1);

  return (
    <div className="flex flex-col items-center justify-between gap-2 px-4 py-3 sm:flex-row">
      <p className="text-sm text-slate-600">
        Showing {Math.min(skip + 1, total)}-{Math.min(skip + limit, total)} of {total}
      </p>
      <div className="flex items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-slate-600">
          Per page
          <select
            value={limit}
            onChange={(e) => onLimitChange(Number(e.target.value))}
            className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm text-slate-700 focus:border-brand-500 focus:outline-none"
          >
            <option value={5}>5</option>
            <option value={10}>10</option>
            <option value={25}>25</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
          </select>
        </label>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onSkipChange(Math.max(skip - limit, 0))}
            disabled={!hasPrev}
          >
            Previous
          </Button>
          <span className="text-sm text-slate-600">
            Page {currentPage} of {totalPages}
          </span>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onSkipChange(skip + limit)}
            disabled={!hasNext}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
