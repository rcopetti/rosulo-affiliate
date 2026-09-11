import { adminApi } from './client';
import { Affiliate } from '../types';

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

export async function getAffiliate(id: string): Promise<Affiliate & { account: { email: string; name: string } }> {
  const res = await adminApi.get<Affiliate & { account: { email: string; name: string } }>(`/admin/affiliates/${id}`);
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

export async function approveKyc(id: string): Promise<void> {
  await adminApi.post(`/admin/affiliates/${id}/approve`);
}

export async function rejectKyc(id: string): Promise<void> {
  await adminApi.post(`/admin/affiliates/${id}/reject`);
}
