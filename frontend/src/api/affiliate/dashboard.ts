import { api } from '../client';
import { Dashboard } from '../types';

export async function getAffiliateDashboard(campaignId?: string | null): Promise<Dashboard> {
  const params = campaignId ? { campaign_id: campaignId } : undefined;
  const res = await api.get<Dashboard>('/affiliate/dashboard', { params });
  return res.data;
}
