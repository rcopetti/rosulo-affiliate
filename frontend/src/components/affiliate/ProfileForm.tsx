import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { AffiliateAccount } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';

const schema = z.object({
  name: z.string().min(1),
  country: z.string().min(1),
  state: z.string().optional(),
  tax_id: z.string().optional(),
  tax_status: z.enum(['us_person', 'non_us_person']),
  tax_form_type: z.enum(['W-9', 'W-8BEN', 'W-8BEN-E']).optional(),
  paypal_email: z.string().email(),
});

export type ProfileFormData = z.infer<typeof schema>;

interface ProfileFormProps {
  account: AffiliateAccount;
  onSubmit: (data: ProfileFormData) => void;
  isLoading?: boolean;
}

export function ProfileForm({ account, onSubmit, isLoading }: ProfileFormProps) {
  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<ProfileFormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: account.name,
      country: account.country || '',
      state: account.state || '',
      tax_id: account.tax_id || '',
      tax_status: account.tax_status || 'us_person',
      tax_form_type: account.tax_form_type,
      paypal_email: account.paypal_email || '',
    },
  });

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <Input label="Full name" {...register('name')} error={errors.name?.message} />
      <Input label="Country" {...register('country')} error={errors.country?.message} />
      <Input label="State / province" {...register('state')} error={errors.state?.message} />
      <Input label="Tax ID" {...register('tax_id')} error={errors.tax_id?.message} />
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1">Tax status</label>
        <Select
          value={account.tax_status || 'us_person'}
          onChange={(v) => setValue('tax_status', v as 'us_person' | 'non_us_person')}
          options={[
            { value: 'us_person', label: 'US person' },
            { value: 'non_us_person', label: 'Non-US person' },
          ]}
        />
      </div>
      <Input label="PayPal email" type="email" {...register('paypal_email')} error={errors.paypal_email?.message} />
      <Button type="submit" isLoading={isLoading}>
        Save profile
      </Button>
    </form>
  );
}
