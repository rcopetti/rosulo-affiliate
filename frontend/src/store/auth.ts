import { AffiliateAccount, Tenant } from '@/api/types';
import { create } from 'zustand';

interface AuthState {
  token: string | null;
  account: AffiliateAccount | null;
  tenants: Tenant[];
  currentTenantId: string | null;
  setAuth: (token: string, account: AffiliateAccount) => void;
  setTenants: (tenants: Tenant[]) => void;
  setTenant: (tenantId: string) => void;
  logout: () => void;
}

function getStored<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    return v ? (JSON.parse(v) as T) : fallback;
  } catch {
    return fallback;
  }
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('rosulo:token'),
  account: getStored<AffiliateAccount | null>('rosulo:account', null),
  tenants: getStored<Tenant[]>('rosulo:tenants', []),
  currentTenantId: localStorage.getItem('rosulo:tenantId'),

  setAuth: (token, account) => {
    localStorage.setItem('rosulo:token', token);
    localStorage.setItem('rosulo:account', JSON.stringify(account));
    set({ token, account });
  },

  setTenants: (tenants) => {
    localStorage.setItem('rosulo:tenants', JSON.stringify(tenants));
    set({ tenants });
  },

  setTenant: (tenantId) => {
    localStorage.setItem('rosulo:tenantId', tenantId);
    set({ currentTenantId: tenantId });
  },

  logout: () => {
    localStorage.removeItem('rosulo:token');
    localStorage.removeItem('rosulo:account');
    localStorage.removeItem('rosulo:tenants');
    localStorage.removeItem('rosulo:tenantId');
    set({ token: null, account: null, tenants: [], currentTenantId: null });
  },
}));
