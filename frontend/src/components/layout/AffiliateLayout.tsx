import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/auth';
import { TenantSelector } from '@/components/shared/TenantSelector';
import { LayoutDashboard, Megaphone, DollarSign, CreditCard, User, LogOut } from 'lucide-react';
import { cn } from '@/lib/utils';

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
    <div className="min-h-screen bg-slate-50">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/80 px-4 py-3 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <Link to="/affiliate/dashboard" className="text-xl font-bold text-brand-700">
            Rosulo Affiliate
          </Link>
          <div className="flex items-center gap-4">
            <TenantSelector />
            <button
              onClick={handleLogout}
              className="inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900"
            >
              <LogOut className="h-4 w-4" />
              Log out
            </button>
          </div>
        </div>
      </header>
      <div className="mx-auto flex max-w-7xl gap-6 p-4 lg:p-8">
        <nav className="hidden w-56 shrink-0 flex-col gap-1 md:flex">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium',
                  isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100'
                )
              }
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <main className="flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
