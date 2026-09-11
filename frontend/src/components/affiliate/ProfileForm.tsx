import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { AffiliateAccount } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { FormField } from '@/components/ui/FormField';
import { FormErrorSummary } from '@/components/ui/FormErrorSummary';

const schema = z.object({
  name: z.string().min(1, 'Full name is required'),
  country: z.string().min(1, 'Country is required'),
  state: z.string().nullish(),
  postal_code: z.string().min(1, 'Postal code is required'),
  tax_id: z.string().nullish(),
  tax_status: z.enum(['us_person', 'foreign_person']).nullish(),
  tax_entity_type: z.enum(['individual', 'business']).nullish(),
  business_name: z.string().nullish(),
  tax_form_type: z.enum(['W-9', 'W-8BEN', 'W-8BEN-E']).nullish(),
  paypal_email: z.string().email('Enter a valid PayPal email'),
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
    watch,
    formState: { errors },
  } = useForm<ProfileFormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: account.name,
      country: account.country || '',
      state: account.state || '',
      postal_code: account.postal_code || '',
      tax_id: account.tax_id || '',
      tax_status: account.tax_status || 'us_person',
      tax_entity_type: account.tax_entity_type || 'individual',
      business_name: account.business_name || '',
      tax_form_type: account.tax_form_type ?? undefined,
      paypal_email: account.paypal_email || '',
    },
  });

  const taxStatus = watch('tax_status') || 'us_person';
  const taxEntityType = watch('tax_entity_type') || 'individual';
  const requiredTaxForm = taxStatus === 'foreign_person'
    ? taxEntityType === 'business' ? 'W-8BEN-E' : 'W-8BEN'
    : 'W-9';

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
      <FormErrorSummary errors={errors} />
      <Input label="Full name" required {...register('name')} error={errors.name?.message} />
      <Input label="Country" required {...register('country')} error={errors.country?.message} />
      <Input label="State / province" {...register('state')} error={errors.state?.message} />
      <Input label="Postal code" required {...register('postal_code')} error={errors.postal_code?.message} />
      <Input label="Tax ID" {...register('tax_id')} error={errors.tax_id?.message} />
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label="Tax status" error={errors.tax_status?.message} helperText="Determines the required IRS form.">
          {(aria) => (
            <div aria-invalid={aria['aria-invalid']} aria-describedby={aria['aria-describedby']}>
              <Select
                value={taxStatus}
                onChange={(v) => setValue('tax_status', v as 'us_person' | 'foreign_person', { shouldValidate: true })}
                options={[
                  { value: 'us_person', label: 'US person' },
                  { value: 'foreign_person', label: 'Foreign person' },
                ]}
              />
            </div>
          )}
        </FormField>
        <FormField label="Payee type" error={errors.tax_entity_type?.message} helperText="Individual or business/entity.">
          {(aria) => (
            <div aria-invalid={aria['aria-invalid']} aria-describedby={aria['aria-describedby']}>
              <Select
                value={taxEntityType}
                onChange={(v) => setValue('tax_entity_type', v as 'individual' | 'business', { shouldValidate: true })}
                options={[
                  { value: 'individual', label: 'Individual' },
                  { value: 'business', label: 'Business/entity' },
                ]}
              />
            </div>
          )}
        </FormField>
      </div>
      {taxEntityType === 'business' && (
        <Input label="Legal business name" {...register('business_name')} error={errors.business_name?.message} />
      )}
      <div className="rounded-lg border border-line bg-surface-muted p-3 text-sm text-fg-muted">
        Required tax form: <strong className="text-fg">{requiredTaxForm}</strong>. Upload it separately below.
      </div>
      <Input
        label="PayPal account (for payouts)"
        type="email"
        required
        {...register('paypal_email')}
        error={errors.paypal_email?.message}
      />
      <Button type="submit" isLoading={isLoading}>
        Save profile
      </Button>
    </form>
  );
}
