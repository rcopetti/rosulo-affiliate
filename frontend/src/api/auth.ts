import { api } from './client';
import { AffiliateAccount, Tenant } from './types';

export interface LoginRequest {
  email: string;
  password: string;
}

export interface AcceptInviteRequest {
  token: string;
  email: string;
  password: string;
  name: string;
  country: string;
  state?: string;
  tax_status?: string;
  tax_form_type?: string;
  paypal_email?: string;
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

export async function acceptInvite(data: AcceptInviteRequest): Promise<AuthResponse> {
  const res = await api.post<AuthResponse>('/auth/affiliate/accept-invite', data);
  return res.data;
}

export async function fetchMerchants(): Promise<Tenant[]> {
  const res = await api.get<Tenant[]>('/affiliate/merchants');
  return res.data;
}

export async function selectMerchant(tenantId: string): Promise<void> {
  await api.post(`/affiliate/merchants/${tenantId}/select`);
}
