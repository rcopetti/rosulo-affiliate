import { api } from '../client';
import { Payout } from '../types';

export async function getPayouts(): Promise<Payout[]> {
  const res = await api.get<Payout[]>('/affiliate/payouts');
  return res.data;
}

export async function requestPayout(currency: string): Promise<Payout> {
  const res = await api.post<Payout>('/affiliate/payout-requests', { currency });
  return res.data;
}
