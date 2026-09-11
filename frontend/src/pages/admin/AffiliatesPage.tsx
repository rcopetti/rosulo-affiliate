import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { getAffiliates } from '@/api/admin/affiliates';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table';
import { KycStatusBadge } from '@/components/shared/KycStatusBadge';

export function AffiliatesPage() {
  const { data, isLoading } = useQuery({ queryKey: ['admin-affiliates'], queryFn: getAffiliates });

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
                <TableHeader>KYC</TableHeader>
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
                    <KycStatusBadge approved={a.kyc_approved_for_payout} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
    </div>
  );
}
