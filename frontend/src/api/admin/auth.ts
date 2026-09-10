import { adminApi } from './client';
import { Tenant } from '@/api/types';

export interface AdminLoginRequest {
  email: string;
  password: string;
}

export interface AdminLoginResponse {
  token: string;
  tenant: Tenant;
}

export interface AdminRegisterRequest {
  tenant_name: string;
  email: string;
  password: string;
  admin_name?: string;
}

export interface AdminRegisterResponse {
  token: string;
  tenant: Tenant;
  user: { id: string; email: string; name?: string; role: string };
  api_key: string;
}

export async function loginAdmin(data: AdminLoginRequest): Promise<AdminLoginResponse> {
  const res = await adminApi.post<AdminLoginResponse>('/auth/tenant/login', data);
  localStorage.setItem('rosulo:adminToken', res.data.token);
  localStorage.setItem('rosulo:adminTenantId', res.data.tenant.id);
  return res.data;
}

export async function registerMerchant(data: AdminRegisterRequest): Promise<AdminRegisterResponse> {
  const res = await adminApi.post<AdminRegisterResponse>('/auth/tenant/register', data);
  localStorage.setItem('rosulo:adminToken', res.data.token);
  localStorage.setItem('rosulo:adminTenantId', res.data.tenant.id);
  localStorage.setItem('rosulo:adminApiKey', res.data.api_key);
  return res.data;
}
