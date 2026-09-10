import { adminApi } from './client';

export interface AdminLoginRequest {
  api_key: string;
  tenant_id: string;
}

export async function loginAdmin(data: AdminLoginRequest): Promise<{ token: string }> {
  const res = await adminApi.post<{ token: string }>('/admin/auth/login', data);
  localStorage.setItem('rosulo:adminToken', res.data.token);
  localStorage.setItem('rosulo:adminTenantId', data.tenant_id);
  return res.data;
}
