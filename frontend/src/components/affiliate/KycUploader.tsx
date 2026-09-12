import { useEffect, useRef, useState } from 'react';
import { uploadDocument, viewDocument } from '@/api/affiliate/profile';
import { AffiliateDocument } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { PdfViewer } from '@/components/ui/PdfViewer';
import { useToast } from '@/components/ui/Toast';
import { formatDateTime } from '@/lib/utils';

interface KycUploaderProps {
  taxStatus?: 'us_person' | 'foreign_person' | null;
  taxEntityType?: 'individual' | 'business' | null;
  documents?: AffiliateDocument[];
  onUpload?: () => void;
}

export function KycUploader({ taxStatus, taxEntityType, documents = [], onUpload }: KycUploaderProps) {
  const [loading, setLoading] = useState(false);
  const [previewLoading, setPreviewLoading] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewType, setPreviewType] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const toast = useToast();
  const requiredType = taxStatus === 'foreign_person' ? taxEntityType === 'business' ? 'W-8BEN-E' : 'W-8BEN' : 'W-9';

  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);

  const preview = async (document: AffiliateDocument) => {
    setPreviewLoading(document.id);
    try {
      const url = await viewDocument(document.id);
      setPreviewUrl(url);
      setPreviewType(document.content_type);
    } catch {
      toast.add({ title: 'Preview failed', description: 'Could not load the encrypted document', variant: 'error' });
    } finally {
      setPreviewLoading(null);
    }
  };

  const handleFile = async (file: File) => {
    setLoading(true);
    try {
      const uploaded = await uploadDocument(file, requiredType);
      const url = await viewDocument(uploaded.id);
      setPreviewUrl(url);
      setPreviewType(uploaded.document_type);
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
      {documents.length > 0 && (
        <div className="space-y-2">
          {[...documents]
            .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
            .map((document, index) => (
            <div key={document.id} className="flex items-center justify-between gap-3 rounded-lg border border-line p-3">
              <div>
                <p className="text-sm font-medium text-fg">
                  {document.document_type}
                  {index === 0 && <span className="ml-2 rounded-full bg-info-soft px-2 py-0.5 text-[10px] font-medium text-info-fg">Most recent</span>}
                </p>
                <p className="text-xs text-fg-muted">
                  Submitted {formatDateTime(document.created_at)} · {document.approved ? 'Approved' : 'Pending review'}
                </p>
              </div>
              <Button variant="secondary" size="sm" onClick={() => preview(document)} isLoading={previewLoading === document.id}>
                View securely
              </Button>
            </div>
          ))}
        </div>
      )}
      <input ref={inputRef} type="file" className="hidden" accept="application/pdf,image/*" aria-label={`Upload ${requiredType}`} onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])} />
      <Button onClick={() => inputRef.current?.click()} isLoading={loading}>
        Replace {requiredType}
      </Button>
      {previewUrl && (
        <div className="overflow-hidden rounded-lg border border-line bg-surface">
          <div className="border-b border-line px-3 py-2 text-xs font-medium text-fg-muted">Secure preview: {previewType}</div>
          {previewType === 'application/pdf' ? (
            <PdfViewer url={previewUrl} title="Secure tax document preview" />
          ) : (
            <img src={previewUrl} alt="Secure tax document preview" className="max-h-[32rem] w-full object-contain" />
          )}
        </div>
      )}
    </div>
  );
}
