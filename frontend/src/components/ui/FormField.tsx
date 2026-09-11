import { ReactNode } from 'react';
import { cn } from '@/lib/utils';

export interface FieldAria {
  id?: string;
  'aria-invalid'?: boolean | 'true' | 'false';
  'aria-describedby'?: string;
}

interface FormFieldProps {
  label?: string;
  htmlFor?: string;
  error?: string;
  helperText?: string;
  required?: boolean;
  className?: string;
  children: (aria: FieldAria) => ReactNode;
}

let fieldCounter = 0;

export function FormField({ label, htmlFor, error, helperText, required, className, children }: FormFieldProps) {
  const fieldId = htmlFor || `field-${++fieldCounter}`;
  const errorId = `${fieldId}-error`;
  const helperId = `${fieldId}-helper`;
  const describedBy = error ? errorId : helperText ? helperId : undefined;

  return (
    <div className={cn('w-full', className)}>
      {label && (
        <label htmlFor={fieldId} className="mb-1 block text-sm font-medium text-fg">
          {label}
          {required && (
            <span className="ml-0.5 text-danger" aria-hidden="true">
              *
            </span>
          )}
        </label>
      )}
      {children({
        id: fieldId,
        'aria-invalid': error ? true : undefined,
        'aria-describedby': describedBy,
      })}
      {error ? (
        <p id={errorId} className="mt-1 text-xs text-danger" role="alert">
          {error}
        </p>
      ) : helperText ? (
        <p id={helperId} className="mt-1 text-xs text-fg-muted">
          {helperText}
        </p>
      ) : null}
    </div>
  );
}
