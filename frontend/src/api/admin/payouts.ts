import { adminApi } from './client';
import { Payout } from '../types';

export async function getAdminPayouts(): Promise<Payout[]> {
  const res = await adminApi.get<Payout[]>('/admin/payouts');
  return res.data;
}

export async function getAdminPayout(id: string): Promise<Payout> {
  const res = await adminApi.get<Payout>(`/admin/payouts/${id}`);
  return res.data;
}

export async function approvePayout(id: string): Promise<Payout> {
  const res = await adminApi.post<Payout>(`/admin/payouts/${id}/approve`);
  return res.data;
}

export async function rejectPayout(id: string): Promise<Payout> {
  const res = await adminApi.post<Payout>(`/admin/payouts/${id}/reject`);
  return res.data;
}
