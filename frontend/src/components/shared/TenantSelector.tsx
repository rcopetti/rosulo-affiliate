import { useAuthStore } from '@/store/auth';
import { useCurrentTenant } from '@/hooks/useCurrentTenant';
import { Select } from '@/components/ui/Select';
import { selectMerchant } from '@/api/auth';

export function TenantSelector() {
  const { tenant, tenants } = useCurrentTenant();
  const setTenant = useAuthStore((s) => s.setTenant);

  const handleChange = async (value: string) => {
    await selectMerchant(value);
    setTenant(value);
    window.location.reload();
  };

  return (
    <Select
      label="Merchant"
      value={tenant?.id}
      onChange={handleChange}
      options={tenants.map((t) => ({ value: t.id, label: t.name }))}
      placeholder="Select merchant"
      className="w-56"
    />
  );
}
