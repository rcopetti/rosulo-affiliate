import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { getAffiliateInvites, getAffiliates } from '@/api/admin/affiliates';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table';
import { KycStatusBadge } from '@/components/shared/KycStatusBadge';
import { formatDate } from '@/lib/utils';

function inviteStatus(expiresAt: string | null) {
  const expired = expiresAt && new Date(expiresAt) < new Date();
  return (
    <span
      className={
        expired
          ? 'inline-flex rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700'
          : 'inline-flex rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700'
      }
    >
      {expired ? 'Expired' : 'Pending'}
    </span>
  );
}

export function AffiliatesPage() {
  const { data, isLoading } = useQuery({ queryKey: ['admin-affiliates'], queryFn: getAffiliates });
  const { data: invites, isLoading: invitesLoading } = useQuery({
    queryKey: ['admin-affiliate-invites'],
    queryFn: getAffiliateInvites,
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Affiliates</h1>
        <Link to="/admin/affiliates/new">
          <Button>Create affiliate</Button>
        </Link>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Affiliate list</CardTitle>
        </CardHeader>
        {isLoading ? (
          <p className="text-sm text-fg-muted">Loading…</p>
        ) : (
          <Table>
            <TableHead>
              <TableRow>
                <TableHeader>Name</TableHeader>
                <TableHeader>Email</TableHeader>
                <TableHeader>Tax document</TableHeader>
              </TableRow>
            </TableHead>
            <TableBody>
              {data?.map((a) => (
                <TableRow key={a.id}>
                  <TableCell>
                    <Link to={`/admin/affiliates/${a.id}`} className="text-brand-600 hover:underline">
                      {a.name}
                    </Link>
                  </TableCell>
                  <TableCell>{a.email}</TableCell>
                  <TableCell>
                    <KycStatusBadge status={a.payout_eligibility.status} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Pending invitations</CardTitle>
        </CardHeader>
        {invitesLoading ? (
          <p className="text-sm text-fg-muted">Loading…</p>
        ) : invites?.length ? (
          <Table>
            <TableHead>
              <TableRow>
                <TableHeader>Email</TableHeader>
                <TableHeader>Invited</TableHeader>
                <TableHeader>Expires</TableHeader>
                <TableHeader>Status</TableHeader>
              </TableRow>
            </TableHead>
            <TableBody>
              {invites.map((invite) => (
                <TableRow key={invite.id}>
                  <TableCell>{invite.email}</TableCell>
                  <TableCell>{formatDate(invite.created_at)}</TableCell>
                  <TableCell>{invite.expires_at ? formatDate(invite.expires_at) : '—'}</TableCell>
                  <TableCell>{inviteStatus(invite.expires_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <p className="text-sm text-fg-muted">No invitations awaiting a response.</p>
        )}
      </Card>
    </div>
  );
}
