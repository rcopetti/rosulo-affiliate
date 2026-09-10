import { useQuery } from '@tanstack/react-query';
import { getAdminEvents } from '@/api/admin/events';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { EventsTable } from '@/components/admin/EventsTable';

export function EventsPage() {
  const { data, isLoading } = useQuery({ queryKey: ['admin-events'], queryFn: () => getAdminEvents() });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-slate-900">Events</h1>
      <Card>
        <CardHeader>
          <CardTitle>Event stream</CardTitle>
        </CardHeader>
        {isLoading ? <p className="p-4 text-slate-600">Loading…</p> : <EventsTable events={data || []} />}
      </Card>
    </div>
  );
}
