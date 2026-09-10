import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { acceptInvite } from '@/api/auth';
import { useAuthStore } from '@/store/auth';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { acceptInviteSchema, AcceptInviteInput } from '@/lib/validators';
import { useToast } from '@/components/ui/Toast';

export function RegisterPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { setAuth, setTenants } = useAuthStore();
  const toast = useToast();

  const token = searchParams.get('token') || '';
  const email = searchParams.get('email') || '';

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<AcceptInviteInput>({
    resolver: zodResolver(acceptInviteSchema),
    defaultValues: {
      token,
      email,
      country: 'US',
      tax_status: 'us_person',
    },
  });

  const mutation = useMutation({
    mutationFn: acceptInvite,
    onSuccess: (data) => {
      setAuth(data.token, data.account);
      setTenants(data.tenants);
      navigate('/merchants');
    },
    onError: () => toast.add({ title: 'Registration failed', description: 'Please check your invite and try again', variant: 'error' }),
  });

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Invalid invite</CardTitle>
          </CardHeader>
          <p className="px-6 pb-6 text-sm text-slate-600">
            Affiliate accounts are created by accepting a tenant invitation.
            Please use the link from your invitation email.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Accept invitation</CardTitle>
        </CardHeader>
        <form onSubmit={handleSubmit((v) => mutation.mutate(v))} className="space-y-4">
          <input type="hidden" {...register('token')} value={token} />
          <Input label="Email" type="email" {...register('email')} error={errors.email?.message} defaultValue={email} />
          <Input label="Password" type="password" {...register('password')} error={errors.password?.message} />
          <Input label="Full name" {...register('name')} error={errors.name?.message} />
          <Input label="Country" {...register('country')} error={errors.country?.message} />
          <Input label="State / province" {...register('state')} error={errors.state?.message} />
          <Button type="submit" isLoading={mutation.isPending} className="w-full">
            Create account
          </Button>
          <p className="text-center text-sm text-slate-600">
            Already registered? <Link to="/login" className="text-brand-600 hover:underline">Log in</Link>
          </p>
        </form>
      </Card>
    </div>
  );
}
