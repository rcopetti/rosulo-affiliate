import { useRef, useState } from 'react';
import { uploadDocument } from '@/api/affiliate/profile';
import { Button } from '@/components/ui/Button';
import { useToast } from '@/components/ui/Toast';

interface KycUploaderProps {
  taxStatus?: 'us_person' | 'foreign_person' | null;
  taxEntityType?: 'individual' | 'business' | null;
  onUpload?: () => void;
}

export function KycUploader({ taxStatus, taxEntityType, onUpload }: KycUploaderProps) {
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const toast = useToast();
  const requiredType = taxStatus === 'foreign_person'
    ? taxEntityType === 'business' ? 'W-8BEN-E' : 'W-8BEN'
    : 'W-9';

  const handleFile = async (file: File) => {
    setLoading(true);
    try {
      await uploadDocument(file, requiredType);
      toast.add({ title: 'Document uploaded', description: `${file.name} uploaded as ${requiredType} for review`, variant: 'success' });
      onUpload?.();
    } catch {
      toast.add({ title: 'Upload failed', description: 'Could not upload document', variant: 'error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-line bg-surface-muted p-3 text-sm text-fg-muted">
        Required document: <strong className="text-fg">{requiredType}</strong>
        <span className="mt-1 block text-xs">This document is reviewed separately from your profile details.</span>
      </div>
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        accept="application/pdf,image/*"
        aria-label={`Upload ${requiredType}`}
        onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
      />
      <Button onClick={() => inputRef.current?.click()} isLoading={loading}>
        Upload {requiredType}
      </Button>
    </div>
  );
}
