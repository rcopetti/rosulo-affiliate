import { api } from '../client';
import { Commission } from '../types';

export async function getCommissions(campaignId?: string | null): Promise<Commission[]> {
  const params = campaignId ? { campaign_id: campaignId } : undefined;
  const res = await api.get<Commission[]>('/affiliate/commissions', { params });
  return res.data;
}
