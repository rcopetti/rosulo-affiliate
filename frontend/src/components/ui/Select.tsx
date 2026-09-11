import * as SelectPrimitive from '@radix-ui/react-select';
import { ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';

interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps {
  value?: string;
  onChange?: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  label?: string;
  className?: string;
}

export function Select({ value, onChange, options, placeholder, label, className }: SelectProps) {
  return (
    <div className={cn('w-full', className)}>
      {label && <label className="mb-1 block text-sm font-medium text-fg">{label}</label>}
      <SelectPrimitive.Root value={value} onValueChange={onChange}>
        <SelectPrimitive.Trigger
          className="inline-flex w-full cursor-pointer items-center justify-between rounded-lg border border-line bg-surface px-3 py-2 text-sm text-fg focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-colors"
          aria-label={label || 'Select'}
        >
          <SelectPrimitive.Value placeholder={placeholder} />
          <SelectPrimitive.Icon>
            <ChevronDown className="h-4 w-4 text-fg-muted" aria-hidden="true" />
          </SelectPrimitive.Icon>
        </SelectPrimitive.Trigger>
        <SelectPrimitive.Portal>
          <SelectPrimitive.Content
            position="popper"
            className="z-50 min-w-[8rem] overflow-hidden rounded-lg border border-line bg-surface shadow-lg"
          >
            <SelectPrimitive.Viewport className="p-1">
              {options.map((o) => (
                <SelectPrimitive.Item
                  key={o.value}
                  value={o.value}
                  className="cursor-pointer rounded px-2 py-1.5 text-sm text-fg outline-none hover:bg-surface-muted focus:bg-surface-muted data-[state=checked]:bg-surface-muted"
                >
                  <SelectPrimitive.ItemText>{o.label}</SelectPrimitive.ItemText>
                </SelectPrimitive.Item>
              ))}
            </SelectPrimitive.Viewport>
          </SelectPrimitive.Content>
        </SelectPrimitive.Portal>
      </SelectPrimitive.Root>
    </div>
  );
}
