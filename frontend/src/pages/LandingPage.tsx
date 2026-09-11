import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';

export function LandingPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      <main className="mx-auto max-w-5xl px-6 py-16 text-center">
        <h1 className="text-4xl font-extrabold tracking-tight text-slate-900 sm:text-5xl">
          Rosulo Affiliate
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-slate-600">
          In-house affiliate tracking for merchants. Invite affiliates, create
          campaigns, track clicks, leads, sales, and pay commissions — all in
          one place.
        </p>

        <div className="mt-12 grid gap-6 sm:grid-cols-2">
          <Card className="text-left">
            <CardHeader>
              <CardTitle>For merchants</CardTitle>
            </CardHeader>
            <div className="space-y-4">
              <p className="text-sm text-slate-600">
                Manage affiliates, track performance, review KYC and approve
                payouts from your tenant dashboard.
              </p>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Button onClick={() => navigate('/admin/register')}>Sign up</Button>
                <Button variant="secondary" onClick={() => navigate('/admin/login')}>Log in</Button>
              </div>
            </div>
          </Card>

          <Card className="text-left">
            <CardHeader>
              <CardTitle>For affiliates</CardTitle>
            </CardHeader>
            <div className="space-y-4">
              <p className="text-sm text-slate-600">
                Accept a tenant invitation, create tracking campaigns, and
                request payouts once your commissions are available.
              </p>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Button onClick={() => navigate('/login')}>Log in</Button>
                <Button variant="secondary" onClick={() => navigate('/register')}>Accept invite</Button>
              </div>
            </div>
          </Card>
        </div>
      </main>
    </div>
  );
}
