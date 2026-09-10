import { adminApi } from './client';

export interface RotateApiKeyResponse {
  api_key: string;
  tenant_id: string;
}

export async function rotateApiKey(): Promise<RotateApiKeyResponse> {
  const res = await adminApi.post<RotateApiKeyResponse>('/admin/integration/api-key');
  return res.data;
}
