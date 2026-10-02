import { api } from '../client';
import { Payout, PayoutRequestPayload } from '../types';

export async function getPayouts(): Promise<Payout[]> {
  const res = await api.get<Payout[]>('/affiliate/payouts');
  return res.data;
}

export async function getPayout(id: string): Promise<Payout> {
  const res = await api.get<Payout>(`/affiliate/payouts/${id}`);
  return res.data;
}

export async function requestPayout(payload: PayoutRequestPayload): Promise<Payout> {
  const res = await api.post<Payout>('/affiliate/payout-requests', payload);
  return res.data;
}
