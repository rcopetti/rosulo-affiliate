import { api } from '../client';
import { Balance } from '../types';

export async function getBalance(): Promise<Balance> {
  const res = await api.get<Balance>('/affiliate/balance');
  return res.data;
}
