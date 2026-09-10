import { adminApi } from './client';
import { Tenant } from '@/api/types';

export interface RotateApiKeyResponse {
  api_key: string;
  tenant_id: string;
}

export interface AllowedDomainsUpdate {
  allowed_domains: string[];
}

export async function getIntegrationTenant(): Promise<Tenant> {
  const res = await adminApi.get<Tenant>('/admin/integration');
  return res.data;
}

export async function updateAllowedDomains(data: AllowedDomainsUpdate): Promise<Tenant> {
  const res = await adminApi.put<Tenant>('/admin/integration/allowed-domains', data);
  return res.data;
}

export async function rotateApiKey(): Promise<RotateApiKeyResponse> {
  const res = await adminApi.post<RotateApiKeyResponse>('/admin/integration/api-key');
  return res.data;
}
