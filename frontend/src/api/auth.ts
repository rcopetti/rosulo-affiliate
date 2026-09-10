import { api } from './client';
import { AffiliateAccount, Tenant } from './types';

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
}

export interface AuthResponse {
  token: string;
  account: AffiliateAccount;
  tenants: Tenant[];
}

export async function loginAffiliate(data: LoginRequest): Promise<AuthResponse> {
  const res = await api.post<AuthResponse>('/auth/affiliate/login', data);
  return res.data;
}

export async function registerAffiliate(data: RegisterRequest): Promise<AuthResponse> {
  const res = await api.post<AuthResponse>('/auth/affiliate/register', data);
  return res.data;
}

export async function fetchMerchants(): Promise<Tenant[]> {
  const res = await api.get<Tenant[]>('/affiliate/merchants');
  return res.data;
}

export async function selectMerchant(tenantId: string): Promise<void> {
  await api.post(`/affiliate/merchants/${tenantId}/select`);
}
