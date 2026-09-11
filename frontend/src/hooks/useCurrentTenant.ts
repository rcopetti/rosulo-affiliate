import { useAuthStore } from '@/store/auth';

export function useCurrentTenant() {
  const { tenants, currentTenantId } = useAuthStore();
  const tenant = tenants.find((t) => t.id === currentTenantId) || null;
  return { tenant, tenants, currentTenantId };
}
