import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/auth';
import { TenantSelector } from '@/components/shared/TenantSelector';
import { PortalShell } from '@/components/layout/PortalShell';
import { LayoutDashboard, Megaphone, DollarSign, CreditCard, User } from 'lucide-react';

const nav = [
  { to: '/affiliate/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/affiliate/campaigns', label: 'Campaigns', icon: Megaphone },
  { to: '/affiliate/balance', label: 'Balance', icon: DollarSign },
  { to: '/affiliate/payouts', label: 'Payouts', icon: CreditCard },
  { to: '/affiliate/profile', label: 'Profile', icon: User },
];

export function AffiliateLayout() {
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <PortalShell
      brand="Rosulo Affiliate"
      brandTo="/affiliate/dashboard"
      nav={nav}
      onLogout={handleLogout}
      topbarRight={<TenantSelector />}
    />
  );
}
