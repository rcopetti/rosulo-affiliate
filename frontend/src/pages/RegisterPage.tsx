import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { registerAffiliate, listInvites, acceptInvite } from '@/api/auth';
import { useAuthStore } from '@/store/auth';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { registerSchema, RegisterInput } from '@/lib/validators';
import { useToast } from '@/components/ui/Toast';
import { FormErrorSummary } from '@/components/ui/FormErrorSummary';
import { PendingInvite } from '@/api/types';

export function RegisterPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { setAuth, setTenants, setTenant, logout } = useAuthStore();
  const toast = useToast();

  const token = searchParams.get('token') || '';
  const email = searchParams.get('email') || '';

  const [step, setStep] = useState<'register' | 'invite' | 'processing'>('register');
  const [invite, setInvite] = useState<PendingInvite | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterInput>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      email,
      country: 'US',
      tax_status: 'us_person',
    },
  });

  const registerMutation = useMutation({
    mutationFn: registerAffiliate,
    onSuccess: async (data) => {
      setAuth(data.token, data.account);
      setTenants(data.tenants);
      try {
        const invites = await listInvites();
        const found = token ? invites.find((i) => i.token === token) : invites[0];
        if (!found) {
          toast.add({
            title: 'No invitation found',
            description: 'Your account was created, but we could not find a matching invite.',
            variant: 'error',
          });
          logout();
          navigate('/login');
          return;
        }
        setInvite(found);
        setStep('invite');
      } catch {
        logout();
        navigate('/login');
      }
    },
    onError: () => toast.add({ title: 'Registration failed', description: 'Please check your details and try again', variant: 'error' }),
  });

  const acceptMutation = useMutation({
    mutationFn: acceptInvite,
    onSuccess: (data) => {
      setAuth(data.token, data.account);
      setTenants(data.tenants);
      if (data.tenants.length === 1) {
        setTenant(data.tenants[0].id);
        navigate('/affiliate/dashboard');
      } else {
        navigate('/merchants');
      }
    },
    onError: () => toast.add({ title: 'Accept failed', description: 'Could not accept the invitation', variant: 'error' }),
  });

  const handleDecline = () => {
    logout();
    navigate('/login');
  };

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Invalid invite</CardTitle>
          </CardHeader>
          <p className="text-sm text-fg-muted">
            Affiliate accounts are created by accepting a tenant invitation.
            Please use the link from your invitation email.
          </p>
        </Card>
      </div>
    );
  }

  if (step === 'invite' && invite) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Accept invitation</CardTitle>
          </CardHeader>
          <div className="space-y-4">
            <p className="text-sm text-slate-600">
              You have been invited to join <strong>{invite.tenant_name}</strong>.
            </p>
            <Button
              onClick={() => acceptMutation.mutate({ token: invite.token })}
              isLoading={acceptMutation.isPending}
              className="w-full"
            >
              Accept invitation
            </Button>
            <Button
              onClick={handleDecline}
              variant="secondary"
              className="w-full"
            >
              Decline and log out
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
          <CardTitle>Create affiliate account</CardTitle>
        </CardHeader>
        <form onSubmit={handleSubmit((v) => registerMutation.mutate(v))} className="space-y-4" noValidate>
          <FormErrorSummary errors={errors} />
          <Input label="Email" type="email" required {...register('email')} error={errors.email?.message} defaultValue={email} />
          <Input label="Password" type="password" required {...register('password')} error={errors.password?.message} />
          <Input label="Full name" required {...register('name')} error={errors.name?.message} />
          <Input label="Country" required {...register('country')} error={errors.country?.message} />
          <Input label="State / province" {...register('state')} error={errors.state?.message} />
          <Button type="submit" isLoading={registerMutation.isPending} className="w-full">
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
