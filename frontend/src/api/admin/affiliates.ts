import { adminApi } from './client';
import { Affiliate, AffiliateDocumentStatus, AffiliatePayoutHistory } from '../types';

export interface CreateInviteRequest {
  email: string;
  name?: string;
  contract_terms?: { payment_sequence: number; commission_percent: number; minimum_threshold?: number }[];
}

export interface InviteOut {
  id: string;
  tenant_id: string;
  email: string;
  token: string;
  contract_terms: { payment_sequence?: number; commission_percent: number }[];
  status: string;
  expires_at: string;
  created_at: string;
}

export async function getAffiliates(): Promise<Affiliate[]> {
  const res = await adminApi.get<Affiliate[]>('/admin/affiliates');
  return res.data;
}

export async function getAffiliate(id: string): Promise<Affiliate> {
  const res = await adminApi.get<Affiliate>(`/admin/affiliates/${id}`);
  return res.data;
}

export async function getAffiliatePayouts(
  id: string,
  params: { limit?: number; offset?: number } = {},
): Promise<AffiliatePayoutHistory> {
  const res = await adminApi.get<AffiliatePayoutHistory>(`/admin/affiliates/${id}/payouts`, { params });
  return res.data;
}

export async function createAffiliate(data: CreateInviteRequest): Promise<InviteOut> {
  const payload = {
    email: data.email,
    contract_terms: data.contract_terms || [
      { payment_sequence: 1, commission_percent: 10 },
    ],
  };
  const res = await adminApi.post<InviteOut>('/admin/affiliates', payload);
  return res.data;
}

export async function updateAffiliate(id: string, data: Partial<Affiliate>): Promise<Affiliate> {
  const res = await adminApi.patch<Affiliate>(`/admin/affiliates/${id}`, data);
  return res.data;
}

export async function viewAffiliateDocument(affiliateId: string, documentId: string): Promise<{ url: string; contentType: string }> {
  const res = await adminApi.get(`/admin/affiliates/${affiliateId}/documents/${documentId}/view`, { responseType: 'blob' });
  return { url: URL.createObjectURL(res.data), contentType: String(res.headers['content-type'] || 'application/octet-stream') };
}

export async function reviewAffiliateDocument(
  affiliateId: string,
  documentId: string,
  data: { status: 'approved' | 'rejected'; rejection_reason?: string },
): Promise<AffiliateDocumentStatus> {
  const res = await adminApi.post<AffiliateDocumentStatus>(
    `/admin/affiliates/${affiliateId}/documents/${documentId}/review`,
    data,
  );
  return res.data;
}
