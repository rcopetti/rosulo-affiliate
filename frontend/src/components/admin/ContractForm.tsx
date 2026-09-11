import { useFieldArray, useForm } from 'react-hook-form';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Term } from '@/api/types';

interface ContractFormProps {
  terms: Term[];
  onSubmit: (data: { terms: Term[] }) => void;
  isLoading?: boolean;
}

export function ContractForm({ terms, onSubmit, isLoading }: ContractFormProps) {
  const { control, register, handleSubmit, getValues } = useForm<{ terms: Term[] }>({
    defaultValues: { terms },
  });
  const { fields, append, remove } = useFieldArray({ control, name: 'terms' });

  // Payment sequences are auto-assigned incrementally to avoid confusion;
  // existing terms are never renumbered because merchants reference them in sale events.
  const nextSequence = () => {
    const values = getValues('terms') || [];
    const nums = values
      .map((t) => parseInt(String(t.payment_sequence), 10))
      .filter((n) => !Number.isNaN(n));
    return String((nums.length ? Math.max(...nums) : 0) + 1);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      {fields.map((field, index) => (
        <div key={field.id} className="grid gap-2 rounded-lg border border-line bg-surface p-4 sm:grid-cols-4">
          <input type="hidden" {...register(`terms.${index}.id`)} defaultValue={field.id} />
          <Input
            label="Sequence"
            readOnly
            helperText="Auto-assigned"
            {...register(`terms.${index}.payment_sequence`)}
          />
          <Input label="Commission %" type="number" required {...register(`terms.${index}.commission_percent`)} />
          <Input label="Min threshold" type="number" {...register(`terms.${index}.minimum_threshold`)} />
          <div className="flex items-end">
            <Button type="button" variant="danger" size="sm" onClick={() => remove(index)}>
              Remove
            </Button>
          </div>
        </div>
      ))}
      <Button
        type="button"
        variant="secondary"
        onClick={() =>
          append({
            id: '',
            payment_sequence: nextSequence(),
            commission_percent: 0,
            minimum_threshold: undefined,
          } as unknown as Term)
        }
      >
        Add term
      </Button>
      <Button type="submit" isLoading={isLoading}>
        Save contract
      </Button>
    </form>
  );
}
