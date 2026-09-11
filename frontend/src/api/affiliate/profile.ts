import { api } from '../client';
import { AffiliateAccount } from '../types';

export async function getProfile(): Promise<AffiliateAccount> {
  const res = await api.get<AffiliateAccount>('/affiliate/profile');
  return res.data;
}

export async function updateProfile(data: Partial<AffiliateAccount>): Promise<AffiliateAccount> {
  const res = await api.patch<AffiliateAccount>('/affiliate/profile', data);
  return res.data;
}

export async function uploadDocument(file: File, type: string): Promise<void> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('type', type);
  await api.post('/affiliate/documents', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
}
