import { useEffect, useRef, useState } from 'react';
import { uploadDocument, viewDocument } from '@/api/affiliate/profile';
import { Button } from '@/components/ui/Button';
import { useToast } from '@/components/ui/Toast';

interface KycUploaderProps {
  taxStatus?: 'us_person' | 'foreign_person' | null;
  taxEntityType?: 'individual' | 'business' | null;
  onUpload?: () => void;
}

export function KycUploader({ taxStatus, taxEntityType, onUpload }: KycUploaderProps) {
  const [loading, setLoading] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewType, setPreviewType] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const toast = useToast();
  const requiredType = taxStatus === 'foreign_person'
    ? taxEntityType === 'business' ? 'W-8BEN-E' : 'W-8BEN'
    : 'W-9';

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  const handleFile = async (file: File) => {
    setLoading(true);
    try {
      const uploaded = await uploadDocument(file, requiredType);
      const url = await viewDocument(uploaded.id);
      setPreviewUrl(url);
      setPreviewType(file.type);
      toast.add({ title: 'Document uploaded', description: `${file.name} uploaded for review`, variant: 'success' });
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
        <span className="mt-1 block text-xs">Documents are encrypted on the server and can only be viewed through this authenticated session. Download is not provided.</span>
      </div>
      <input ref={inputRef} type="file" className="hidden" accept="application/pdf,image/*" aria-label={`Upload ${requiredType}`} onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])} />
      <Button onClick={() => inputRef.current?.click()} isLoading={loading}>
        Replace {requiredType}
      </Button>
      {previewUrl && (
        <div className="overflow-hidden rounded-lg border border-line bg-surface">
          <div className="border-b border-line px-3 py-2 text-xs font-medium text-fg-muted">Secure preview</div>
          {previewType === 'application/pdf' ? (
            <iframe title={`${requiredType} secure preview`} src={`${previewUrl}#toolbar=0&download=0&navpanes=0`} className="h-[32rem] w-full" />
          ) : (
            <img src={previewUrl} alt={`${requiredType} secure preview`} className="max-h-[32rem] w-full object-contain" />
          )}
        </div>
      )}
    </div>
  );
}
