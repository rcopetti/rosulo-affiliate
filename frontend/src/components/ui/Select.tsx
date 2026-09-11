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
      {label && <label className="block text-sm font-medium text-slate-700 mb-1">{label}</label>}
      <SelectPrimitive.Root value={value} onValueChange={onChange}>
        <SelectPrimitive.Trigger
          className="inline-flex w-full items-center justify-between rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none"
          aria-label={label || 'Select'}
        >
          <SelectPrimitive.Value placeholder={placeholder} />
          <SelectPrimitive.Icon>
            <ChevronDown className="h-4 w-4 text-slate-500" />
          </SelectPrimitive.Icon>
        </SelectPrimitive.Trigger>
        <SelectPrimitive.Portal>
          <SelectPrimitive.Content
            position="popper"
            className="z-50 min-w-[8rem] overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg"
          >
            <SelectPrimitive.Viewport className="p-1">
              {options.map((o) => (
                <SelectPrimitive.Item
                  key={o.value}
                  value={o.value}
                  className="cursor-pointer rounded px-2 py-1.5 text-sm text-slate-700 outline-none hover:bg-slate-100 focus:bg-slate-100 data-[state=checked]:bg-slate-100"
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
