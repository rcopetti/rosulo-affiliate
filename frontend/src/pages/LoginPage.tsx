import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { affiliateReturnTenantId, loginAffiliate, safeAffiliateReturnTo, selectMerchant } from '@/api/auth';
import { useAuthStore } from '@/store/auth';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { loginSchema, LoginInput } from '@/lib/validators';
import { useToast } from '@/components/ui/Toast';

export function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { setAuth } = useAuthStore();
  const toast = useToast();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginInput>({ resolver: zodResolver(loginSchema) });

  const mutation = useMutation({
    mutationFn: loginAffiliate,
    onSuccess: async (data) => {
      setAuth(data.token, data.account);
      localStorage.setItem('rosulo:tenants', JSON.stringify(data.tenants));
      const returnToParam = searchParams.get('returnTo');
      // Honor a preserved deep link only when it is an affiliate payout
      // path whose tenant_id matches a merchant this affiliate belongs to.
      // The API still verifies ownership; the link selects nothing it
      // couldn't already reach.
      const returnTo = safeAffiliateReturnTo(
        returnToParam,
        data.tenants.map((tenant) => tenant.id)
      );
      if (returnTo) {
        const tenantId = affiliateReturnTenantId(returnTo) as string;
        await selectMerchant(tenantId).catch(() => undefined);
        useAuthStore.getState().setTenant(tenantId);
        navigate(returnTo);
      } else if (data.tenants.length === 1) {
        useAuthStore.getState().setTenant(data.tenants[0].id);
        navigate('/affiliate/dashboard');
      } else {
        navigate(
          returnToParam
            ? `/merchants?returnTo=${encodeURIComponent(returnToParam)}`
            : '/merchants'
        );
      }
    },
    onError: () => toast.add({ title: 'Login failed', description: 'Check your credentials', variant: 'error' }),
  });

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Affiliate Login</CardTitle>
        </CardHeader>
        <form onSubmit={handleSubmit((v) => mutation.mutate(v))} className="space-y-4">
          <Input label="Email" type="email" {...register('email')} error={errors.email?.message} />
          <Input label="Password" type="password" {...register('password')} error={errors.password?.message} />
          <Button type="submit" isLoading={mutation.isPending} className="w-full">
            Log in
          </Button>
          <p className="text-center text-sm text-slate-600">
            Don't have an account? <Link to="/register" className="text-brand-600 hover:underline">Register</Link>
          </p>
          <p className="text-center text-sm text-slate-600">
            <Link to="/forgot-password" className="text-brand-600 hover:underline">
              Forgot password?
            </Link>
          </p>
        </form>
      </Card>
    </div>
  );
}
