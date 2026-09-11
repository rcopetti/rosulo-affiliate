import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { registerMerchant } from '@/api/admin/auth';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { useToast } from '@/components/ui/Toast';

export function AdminRegisterPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const [tenantName, setTenantName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [adminName, setAdminName] = useState('');
  const [loading, setLoading] = useState(false);
  const [apiKey, setApiKey] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await registerMerchant({
        tenant_name: tenantName,
        email,
        password,
        admin_name: adminName,
      });
      setApiKey(res.api_key);
      toast.add({ title: 'Tenant created', description: 'Save your API key — it is shown only once.', variant: 'success' });
    } catch {
      toast.add({ title: 'Registration failed', description: 'Please check your details and try again', variant: 'error' });
    } finally {
      setLoading(false);
    }
  };

  if (apiKey) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Your API key</CardTitle>
          </CardHeader>
          <div className="space-y-4 px-6 pb-6">
            <p className="text-sm text-slate-600">
              Copy this key now. It will not be shown again and is required for server-to-server event ingestion.
            </p>
            <pre className="break-all rounded-md bg-slate-100 p-3 text-sm">{apiKey}</pre>
            <Button className="w-full" onClick={() => navigate('/admin/dashboard')}>
              Go to dashboard
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Merchant sign up</CardTitle>
        </CardHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Company / tenant name"
            value={tenantName}
            onChange={(e) => setTenantName(e.target.value)}
            required
          />
          <Input
            label="Admin name"
            value={adminName}
            onChange={(e) => setAdminName(e.target.value)}
          />
          <Input
            label="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />
          <Button type="submit" isLoading={loading} className="w-full">
            Create tenant
          </Button>
          <p className="text-center text-sm text-slate-600">
            Already have an account? <Link to="/admin/login" className="text-brand-600 hover:underline">Log in</Link>
          </p>
        </form>
      </Card>
    </div>
  );
}
