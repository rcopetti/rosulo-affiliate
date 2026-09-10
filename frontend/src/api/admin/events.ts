import { adminApi } from './client';
import { Event } from '../types';

export interface EventFilters {
  type?: 'click' | 'lead' | 'sale';
  campaign_id?: string;
  affiliate_id?: string;
  from?: string;
  to?: string;
}

export async function getAdminEvents(filters?: EventFilters): Promise<Event[]> {
  const res = await adminApi.get<Event[]>('/admin/events', { params: filters });
  return res.data;
}
