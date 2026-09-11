import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getAdminEvents } from '@/api/admin/events';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { EventsTable } from '@/components/admin/EventsTable';
import { Pagination } from '@/components/ui/Pagination';
import { Skeleton } from '@/components/ui/Skeleton';
import { cn } from '@/lib/utils';

const typeFilters = [
  { value: undefined, label: 'All' },
  { value: 'click', label: 'Clicks' },
  { value: 'lead', label: 'Leads' },
  { value: 'sale', label: 'Sales' },
] as const;

export function EventsPage() {
  const [skip, setSkip] = useState(0);
  const [limit, setLimit] = useState(20);
  const [type, setType] = useState<string | undefined>(undefined);
  const { data, isLoading } = useQuery({
    queryKey: ['admin-events', skip, limit, type],
    queryFn: () => getAdminEvents(type ? { type: type as 'click' | 'lead' | 'sale' } : undefined, { skip, limit }),
  });

  const handleLimitChange = (newLimit: number) => {
    setLimit(newLimit);
    setSkip(0);
  };

  const handleTypeChange = (value: string | undefined) => {
    setType(value);
    setSkip(0);
  };

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-fg">Events</h1>
      <Card>
        <CardHeader
          action={
            <div className="flex gap-1 rounded-lg bg-surface-muted p-1" role="group" aria-label="Filter by event type">
              {typeFilters.map((f) => (
                <button
                  key={f.label}
                  type="button"
                  onClick={() => handleTypeChange(f.value)}
                  aria-pressed={type === f.value}
                  className={cn(
                    'cursor-pointer rounded-md px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary',
                    type === f.value
                      ? 'bg-surface text-fg shadow-sm'
                      : 'text-fg-muted hover:text-fg'
                  )}
                >
                  {f.label}
                </button>
              ))}
            </div>
          }
        >
          <CardTitle>Event stream</CardTitle>
        </CardHeader>
        {isLoading ? (
          <TableSkeletonInline />
        ) : (
          <div className="space-y-2">
            <EventsTable events={data?.items || []} />
            {data && (
              <Pagination
                skip={data.skip}
                limit={data.limit}
                total={data.total}
                onSkipChange={setSkip}
                onLimitChange={handleLimitChange}
              />
            )}
          </div>
        )}
      </Card>
    </div>
  );
}

function TableSkeletonInline() {
  return (
    <div className="divide-y divide-line" role="status" aria-label="Loading events">
      {Array.from({ length: 6 }).map((_, r) => (
        <div key={r} className="flex items-center gap-4 px-4 py-3">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-4 flex-1" />
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-24" />
        </div>
      ))}
    </div>
  );
}
