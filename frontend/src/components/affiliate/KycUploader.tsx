import { useEffect, useRef, useState } from 'react';
import { uploadDocument, viewDocument } from '@/api/affiliate/profile';
import { AffiliateDocument, PayoutEligibility } from '@/api/types';
import { KycStatusBadge } from '@/components/shared/KycStatusBadge';
import { Button } from '@/components/ui/Button';
import { PdfViewer } from '@/components/ui/PdfViewer';
import { useToast } from '@/components/ui/Toast';
import { formatDateTime } from '@/lib/utils';

const IRS_FORM_URLS: Record<string, string> = {
  'W-8BEN': 'https://www.irs.gov/pub/irs-pdf/fw8ben.pdf',
  'W-8BEN-E': 'https://www.irs.gov/pub/irs-pdf/fw8bene.pdf',
  'W-9': 'https://www.irs.gov/pub/irs-pdf/fw9.pdf',
};

interface KycUploaderProps {
  requiredDocumentType?: string;
  documents?: AffiliateDocument[];
  payoutEligibility?: PayoutEligibility;
  isLoading?: boolean;
  onUpload?: () => void;
}

export function KycUploader({
  requiredDocumentType,
  documents = [],
  payoutEligibility,
  isLoading = false,
  onUpload,
}: KycUploaderProps) {
  const [loading, setLoading] = useState(false);
  const [previewLoading, setPreviewLoading] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewType, setPreviewType] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const toast = useToast();
  const requiredType = requiredDocumentType || 'W-9';
  const hasSubmittedRequired = documents.some((d) => d.document_type === requiredType);

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
        {IRS_FORM_URLS[requiredType] && (
          <a
            href={IRS_FORM_URLS[requiredType]}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-2 text-primary hover:underline"
          >
            Download blank {requiredType} (irs.gov)
          </a>
        )}
        <span className="mt-1 block text-xs">Documents are encrypted on the server and can only be viewed through this authenticated session. Download is not provided.</span>
      </div>
      {payoutEligibility && (
        <p className="flex items-center gap-2 text-sm text-fg-muted">
          Tax document status: <KycStatusBadge status={payoutEligibility.status} />
        </p>
      )}
      {isLoading ? (
        <p className="text-sm text-fg-muted">Loading tax documents…</p>
      ) : documents.length > 0 && (
        <div className="space-y-2">
          {[...documents]
            .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
            .map((document, index) => (
              <div key={document.id} className="flex items-start justify-between gap-3 rounded-lg border border-line p-3">
                <div>
                  <p className="text-sm font-medium text-fg">
                    {document.document_type}
                    {index === 0 && <span className="ml-2 rounded-full bg-info-soft px-2 py-0.5 text-[10px] font-medium text-info-fg">Most recent</span>}
                  </p>
                  <p className="text-xs text-fg-muted">
                    Submitted {formatDateTime(document.created_at)} · {document.status === 'approved' ? 'Approved' : document.status === 'rejected' ? 'Rejected' : 'Pending review'}
                  </p>
                  {document.review_history.map((review, reviewIndex) => (
                    <p key={`${document.id}-${reviewIndex}`} className="mt-1 text-xs text-fg-muted">
                      Reviewed {formatDateTime(review.reviewed_at)} by {review.reviewer.name || review.reviewer.email}: {review.status}
                      {review.rejection_reason ? ` · ${review.rejection_reason}` : ''}
                    </p>
                  ))}
                </div>
                <Button variant="secondary" size="sm" onClick={() => preview(document)} isLoading={previewLoading === document.id}>
                  View securely
                </Button>
              </div>
            ))}
        </div>
      )}
      <input ref={inputRef} type="file" className="hidden" accept=".pdf,image/jpeg,image/png,image/webp" aria-label={`Upload ${requiredType}`} onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])} />
      <Button onClick={() => inputRef.current?.click()} isLoading={loading} disabled={isLoading || !requiredDocumentType}>
        {hasSubmittedRequired ? `Replace ${requiredType}` : `Submit ${requiredType}`}
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
