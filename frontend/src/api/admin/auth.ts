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

export async function loginAdmin(data: AdminLoginRequest): Promise<AdminLoginResponse> {
  const res = await adminApi.post<AdminLoginResponse>('/auth/tenant/login', data);
  localStorage.setItem('rosulo:adminToken', res.data.token);
  localStorage.setItem('rosulo:adminTenantId', res.data.tenant.id);
  return res.data;
}
