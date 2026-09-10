import { Select } from '@/components/ui/Select';

interface TaxStatusSelectorProps {
  value: 'us_person' | 'non_us_person';
  onChange: (value: 'us_person' | 'non_us_person') => void;
}

export function TaxStatusSelector({ value, onChange }: TaxStatusSelectorProps) {
  return (
    <Select
      label="Tax status"
      value={value}
      onChange={(v) => onChange(v as 'us_person' | 'non_us_person')}
      options={[
        { value: 'us_person', label: 'US person (W-9)' },
        { value: 'non_us_person', label: 'Non-US person (W-8BEN)' },
      ]}
    />
  );
}
