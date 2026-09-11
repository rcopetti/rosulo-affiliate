import { useRef, useState } from 'react';
import { uploadDocument } from '@/api/affiliate/profile';
import { Button } from '@/components/ui/Button';
import { FormField } from '@/components/ui/FormField';
import { useToast } from '@/components/ui/Toast';

interface KycUploaderProps {
  onUpload?: () => void;
}

const documentTypes = [
  { value: 'W-9', label: 'W-9' },
  { value: 'W-8BEN', label: 'W-8BEN' },
  { value: 'W-8BEN-E', label: 'W-8BEN-E' },
  { value: 'identity', label: 'Proof of identity' },
];

export function KycUploader({ onUpload }: KycUploaderProps) {
  const [type, setType] = useState('W-9');
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const toast = useToast();

  const handleFile = async (file: File) => {
    setLoading(true);
    try {
      await uploadDocument(file, type);
      toast.add({ title: 'Document uploaded', description: `${file.name} uploaded for review`, variant: 'success' });
      onUpload?.();
    } catch {
      toast.add({ title: 'Upload failed', description: 'Could not upload document', variant: 'error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-2">
      <FormField label="Document type" helperText="US persons need a W-9; non-US individuals need a W-8BEN.">
        {(aria) => (
          <select
            id={aria.id}
            aria-describedby={aria['aria-describedby']}
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="w-full cursor-pointer rounded-lg border border-line bg-surface px-3 py-2 text-sm text-fg focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          >
            {documentTypes.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        )}
      </FormField>
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        aria-label="Tax document file"
        onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
      />
      <Button onClick={() => inputRef.current?.click()} isLoading={loading}>
        Upload document
      </Button>
    </div>
  );
}
