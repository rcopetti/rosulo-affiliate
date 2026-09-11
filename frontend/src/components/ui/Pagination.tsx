import { Button } from './Button';

interface PaginationProps {
  skip: number;
  limit: number;
  total: number;
  onSkipChange: (skip: number) => void;
}

export function Pagination({ skip, limit, total, onSkipChange }: PaginationProps) {
  const hasPrev = skip > 0;
  const hasNext = skip + limit < total;
  const currentPage = Math.floor(skip / limit) + 1;
  const totalPages = Math.ceil(total / limit);

  return (
    <div className="flex items-center justify-between px-4 py-3">
      <p className="text-sm text-slate-600">
        Showing {Math.min(skip + 1, total)}-{Math.min(skip + limit, total)} of {total}
      </p>
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
  );
}
