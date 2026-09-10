import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { useNavigate, Link } from 'react-router-dom';
import { registerAffiliate } from '@/api/auth';
import { useAuthStore } from '@/store/auth';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';
import { registerSchema, RegisterInput } from '@/lib/validators';
import { useToast } from '@/components/ui/Toast';

export function RegisterPage() {
  const navigate = useNavigate();
  const { setAuth } = useAuthStore();
  const toast = useToast();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterInput>({ resolver: zodResolver(registerSchema) });

  const mutation = useMutation({
    mutationFn: registerAffiliate,
    onSuccess: (data) => {
      setAuth(data.token, data.account);
      navigate('/merchants');
    },
    onError: () => toast.add({ title: 'Registration failed', description: 'Please try again', variant: 'error' }),
  });

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Register as an Affiliate</CardTitle>
        </CardHeader>
        <form onSubmit={handleSubmit((v) => mutation.mutate(v))} className="space-y-4">
          <Input label="Full name" {...register('name')} error={errors.name?.message} />
          <Input label="Email" type="email" {...register('email')} error={errors.email?.message} />
          <Input label="Password" type="password" {...register('password')} error={errors.password?.message} />
          <Input label="Country" {...register('country')} error={errors.country?.message} />
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
