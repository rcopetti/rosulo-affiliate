import { api } from '../client';
import { Payout } from '../types';

export async function getPayouts(): Promise<Payout[]> {
  const res = await api.get<Payout[]>('/affiliate/payouts');
  return res.data;
}

export async function requestPayout(amount: number): Promise<Payout> {
  const res = await api.post<Payout>('/affiliate/payout-requests', { amount });
  return res.data;
}
