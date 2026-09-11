import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { FormErrorSummary } from '@/components/ui/FormErrorSummary';
import { Campaign } from '@/api/types';

const schema = z.object({
  name: z.string().min(1, 'Name is required'),
  landing_url: z.string().url('Invalid URL').optional().or(z.literal('')),
});

export type CampaignFormData = z.infer<typeof schema>;

interface CampaignFormProps {
  campaign?: Campaign;
  onSubmit: (data: CampaignFormData) => void;
  isLoading?: boolean;
}

export function CampaignForm({ campaign, onSubmit, isLoading }: CampaignFormProps) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<CampaignFormData>({
    resolver: zodResolver(schema),
    defaultValues: { name: campaign?.name || '', landing_url: campaign?.landing_url || '' },
  });

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
      <FormErrorSummary errors={errors} />
      <Input label="Name" required {...register('name')} error={errors.name?.message} />
      <Input
        label="Landing URL"
        type="url"
        helperText="Where affiliates will send traffic, e.g. https://example.com/promo"
        {...register('landing_url')}
        error={errors.landing_url?.message}
      />
      <Button type="submit" isLoading={isLoading}>
        {campaign ? 'Update campaign' : 'Create campaign'}
      </Button>
    </form>
  );
}
