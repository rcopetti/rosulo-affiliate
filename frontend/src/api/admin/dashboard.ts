import { adminApi } from './client';
import { AdminDashboard } from '../types';

export async function getAdminDashboard(): Promise<AdminDashboard> {
  const res = await adminApi.get<AdminDashboard>('/admin/dashboard');
  return res.data;
}
