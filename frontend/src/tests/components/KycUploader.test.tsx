import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { KycUploader } from '@/components/affiliate/KycUploader';
import { ToastProvider } from '@/components/ui/Toast';

const documentStatus = {
  required_document_type: 'W-9',
  documents: [{
    id: 'doc-1',
    document_type: 'W-9',
    content_type: 'application/pdf',
    created_at: '2026-10-01T00:00:00Z',
    status: 'rejected' as const,
    review_history: [{
      status: 'rejected' as const,
      reviewed_at: '2026-10-01T00:00:00Z',
      rejection_reason: 'The form is unsigned',
      reviewer: { id: 'reviewer-1', name: 'Merchant Reviewer', email: 'reviewer@example.com' },
    }],
  }],
  payout_eligibility: {
    eligible: false,
    status: 'rejected' as const,
    reason: 'The form is unsigned',
  },
};

describe('KycUploader', () => {
  it('shows merchant review status and rejection reason from the API', () => {
    render(
      <ToastProvider>
        <KycUploader
          requiredDocumentType="W-9"
          documents={documentStatus.documents}
          payoutEligibility={documentStatus.payout_eligibility}
          isLoading={false}
        />
      </ToastProvider>
    );

    expect(screen.getByText('Tax form rejected')).toBeInTheDocument();
    expect(screen.getByText(/The form is unsigned/)).toBeInTheDocument();
  });

  it('keeps uploads disabled until the backend provides the required form', () => {
    render(
      <ToastProvider>
        <KycUploader isLoading={false} />
      </ToastProvider>
    );

    expect(screen.getByRole('button', { name: /submit/i })).toBeDisabled();
  });

  it('offers Submit before the required form exists and Replace after', () => {
    const { rerender } = render(
      <ToastProvider>
        <KycUploader requiredDocumentType="W-9" documents={[]} isLoading={false} />
      </ToastProvider>
    );

    expect(
      screen.getByRole('button', { name: 'Submit W-9' })
    ).toBeInTheDocument();

    rerender(
      <ToastProvider>
        <KycUploader
          requiredDocumentType="W-9"
          documents={documentStatus.documents}
          isLoading={false}
        />
      </ToastProvider>
    );

    expect(
      screen.getByRole('button', { name: 'Replace W-9' })
    ).toBeInTheDocument();
  });

  it('links the required form to its IRS PDF', () => {
    render(
      <ToastProvider>
        <KycUploader requiredDocumentType="W-8BEN-E" documents={[]} isLoading={false} />
      </ToastProvider>
    );

    const link = screen.getByRole('link', { name: /W-8BEN-E/i });
    expect(link).toHaveAttribute(
      'href',
      'https://www.irs.gov/pub/irs-pdf/fw8bene.pdf'
    );
    expect(link).toHaveAttribute('target', '_blank');
  });
});
