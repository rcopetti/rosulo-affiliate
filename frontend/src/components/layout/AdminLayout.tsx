import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { LayoutDashboard, Users, CreditCard, Activity, Key, LogOut } from 'lucide-react';
import { cn } from '@/lib/utils';

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
    <div className="min-h-screen bg-slate-50">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/80 px-4 py-3 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <Link to="/admin/dashboard" className="text-xl font-bold text-brand-700">
            Rosulo Admin
          </Link>
          <button
            onClick={handleLogout}
            className="inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900"
          >
            <LogOut className="h-4 w-4" />
            Log out
          </button>
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
