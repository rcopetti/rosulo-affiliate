import { adminApi } from './client';
import { Affiliate, AffiliateAccount } from '../types';

export interface CreateAffiliateRequest {
  email: string;
  name: string;
  contract: { terms: { payment_sequence: string; commission_percent: number }[] };
}

export async function getAffiliates(): Promise<Affiliate[]> {
  const res = await adminApi.get<Affiliate[]>('/admin/affiliates');
  return res.data;
}

export async function getAffiliate(id: string): Promise<Affiliate & { account: AffiliateAccount }> {
  const res = await adminApi.get<Affiliate & { account: AffiliateAccount }>(`/admin/affiliates/${id}`);
  return res.data;
}

export async function createAffiliate(data: CreateAffiliateRequest): Promise<Affiliate> {
  const res = await adminApi.post<Affiliate>('/admin/affiliates', data);
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
