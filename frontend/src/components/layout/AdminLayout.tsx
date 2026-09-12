import { useNavigate } from 'react-router-dom';
import { PortalShell } from '@/components/layout/PortalShell';
import { LayoutDashboard, Users, CreditCard, Activity, Key } from 'lucide-react';

const nav = [
  { to: '/admin/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/admin/affiliates', label: 'Affiliates', icon: Users },
  { to: '/admin/payouts', label: 'Payouts', icon: CreditCard },
  { to: '/admin/events', label: 'Events', icon: Activity },
  { to: '/admin/integration', label: 'Integration', icon: Key },
];

export function AdminLayout() {
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem('rosulo:adminToken');
    localStorage.removeItem('rosulo:adminTenantId');
    navigate('/admin/login');
  };

  return (
    <PortalShell
      brand="Rosulo Admin"
      brandTo="/admin/dashboard"
      nav={nav}
      onLogout={handleLogout}
    />
  );
}
