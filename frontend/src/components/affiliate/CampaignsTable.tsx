import { Campaign } from '@/api/types';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table';
import { Link } from 'react-router-dom';

export function CampaignsTable({ campaigns }: { campaigns: Campaign[] }) {
  return (
    <Table>
      <TableHead>
        <TableRow>
          <TableHeader>Name</TableHeader>
          <TableHeader>Tracking code</TableHeader>
          <TableHeader>Landing URL</TableHeader>
          <TableHeader>Created</TableHeader>
        </TableRow>
      </TableHead>
      <TableBody>
        {campaigns.map((c) => (
          <TableRow key={c.id}>
            <TableCell>
              <Link to={`/affiliate/campaigns/${c.id}`} className="text-brand-600 hover:underline">
                {c.name}
              </Link>
            </TableCell>
            <TableCell>{c.tracking_code}</TableCell>
            <TableCell>{c.landing_url || '-'}</TableCell>
            <TableCell>{new Date(c.created_at).toLocaleDateString()}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
