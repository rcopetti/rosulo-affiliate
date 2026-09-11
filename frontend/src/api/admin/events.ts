import { adminApi } from './client';
import { PaginatedEvents } from '../types';

export interface EventFilters {
  type?: 'click' | 'lead' | 'sale';
  campaign_id?: string;
  affiliate_id?: string;
  from?: string;
  to?: string;
}

export interface PaginationParams {
  skip: number;
  limit: number;
}

export async function getAdminEvents(
  filters?: EventFilters,
  pagination: PaginationParams = { skip: 0, limit: 20 }
): Promise<PaginatedEvents> {
  const res = await adminApi.get<PaginatedEvents>('/admin/events', {
    params: { ...filters, ...pagination },
  });
  return res.data;
}
