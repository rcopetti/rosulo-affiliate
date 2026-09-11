import { FieldErrors } from 'react-hook-form';

interface FormErrorSummaryProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  errors: FieldErrors<any>;
  title?: string;
}

export function FormErrorSummary({ errors, title = 'Please fix the following before continuing' }: FormErrorSummaryProps) {
  const entries = Object.entries(errors).filter(
    ([, e]) => e && typeof e === 'object' && 'message' in e && Boolean((e as { message?: string }).message)
  );
  if (entries.length === 0) return null;

  return (
    <div role="alert" className="rounded-lg border border-danger/30 bg-danger-soft p-4">
      <p className="text-sm font-semibold text-danger-fg">{title}</p>
      <ul className="mt-1 list-inside list-disc space-y-0.5 text-sm text-danger-fg">
        {entries.map(([field, e]) => (
          <li key={field}>{(e as { message?: string }).message || `Invalid value for ${field}`}</li>
        ))}
      </ul>
    </div>
  );
}
