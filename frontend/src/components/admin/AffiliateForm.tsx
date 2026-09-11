import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';

const schema = z.object({
  email: z.string().email(),
});

export type AffiliateFormData = z.infer<typeof schema>;

interface AffiliateFormProps {
  onSubmit: (data: AffiliateFormData) => void;
  isLoading?: boolean;
}

export function AffiliateForm({ onSubmit, isLoading }: AffiliateFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<AffiliateFormData>({ resolver: zodResolver(schema) });

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <Input label="Email" type="email" {...register('email')} error={errors.email?.message} />
      <Button type="submit" isLoading={isLoading}>
        Send invite
      </Button>
    </form>
  );
}
