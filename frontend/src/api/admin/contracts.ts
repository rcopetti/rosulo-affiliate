import { adminApi } from './client';
import { Contract, Term } from '../types';

export async function getContract(affiliateId: string): Promise<Contract> {
  const res = await adminApi.get<Contract>(`/admin/affiliates/${affiliateId}/contract`);
  return res.data;
}

export async function updateContract(affiliateId: string, contract: Contract): Promise<Contract> {
  const res = await adminApi.put<Contract>(`/admin/affiliates/${affiliateId}/contract`, contract);
  return res.data;
}

export async function addTerm(affiliateId: string, term: Omit<Term, 'id'>): Promise<Term> {
  const res = await adminApi.post<Term>(`/admin/affiliates/${affiliateId}/contract/terms`, term);
  return res.data;
}
