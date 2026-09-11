import { api } from '../client';
import { Campaign } from '../types';

export interface CampaignCreate {
  name: string;
  landing_url?: string;
}

export async function getCampaigns(): Promise<Campaign[]> {
  const res = await api.get<Campaign[]>('/affiliate/campaigns');
  return res.data;
}

export async function getCampaign(id: string): Promise<Campaign> {
  const res = await api.get<Campaign>(`/affiliate/campaigns/${id}`);
  return res.data;
}

export async function createCampaign(data: CampaignCreate): Promise<Campaign> {
  const res = await api.post<Campaign>('/affiliate/campaigns', data);
  return res.data;
}

export async function updateCampaign(id: string, data: CampaignCreate): Promise<Campaign> {
  const res = await api.patch<Campaign>(`/affiliate/campaigns/${id}`, data);
  return res.data;
}
