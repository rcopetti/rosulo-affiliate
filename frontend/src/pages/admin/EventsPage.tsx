import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getAdminEvents } from '@/api/admin/events';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { EventsTable } from '@/components/admin/EventsTable';
import { Pagination } from '@/components/ui/Pagination';

export function EventsPage() {
  const [skip, setSkip] = useState(0);
  const [limit, setLimit] = useState(20);
  const { data, isLoading } = useQuery({
    queryKey: ['admin-events', skip, limit],
    queryFn: () => getAdminEvents(undefined, { skip, limit }),
  });

  const handleLimitChange = (newLimit: number) => {
    setLimit(newLimit);
    setSkip(0);
  };

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-slate-900">Events</h1>
      <Card>
        <CardHeader>
          <CardTitle>Event stream</CardTitle>
        </CardHeader>
        {isLoading ? (
          <p className="p-4 text-slate-600">Loading…</p>
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
