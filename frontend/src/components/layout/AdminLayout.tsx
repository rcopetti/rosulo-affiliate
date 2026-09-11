import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { LayoutDashboard, Users, CreditCard, Activity, Key, LogOut } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ThemeToggle } from '@/components/ui/ThemeToggle';
import { Button } from '@/components/ui/Button';

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
    <div className="min-h-screen bg-bg">
      <header className="sticky top-0 z-30 border-b border-line bg-surface/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4">
          <Link to="/admin/dashboard" className="flex items-center gap-2 text-lg font-bold text-primary">
            <img src="/logo.svg" alt="" className="h-6 w-6" aria-hidden="true" />
            Rosulo Admin
          </Link>
          <div className="flex items-center gap-1">
            <ThemeToggle />
            <Button variant="ghost" size="sm" onClick={handleLogout}>
              <LogOut className="h-4 w-4" aria-hidden="true" />
              Log out
            </Button>
          </div>
        </div>
      </header>
      <div className="mx-auto flex max-w-7xl gap-6 p-4 lg:p-8">
        <nav className="hidden w-56 shrink-0 flex-col gap-1 md:flex" aria-label="Admin navigation">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-brand-50 text-brand-700 dark:bg-primary/10 dark:text-brand-300'
                    : 'text-fg-muted hover:bg-surface-muted hover:text-fg'
                )
              }
            >
              <item.icon className="h-4 w-4" aria-hidden="true" />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <main className="min-w-0 flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
