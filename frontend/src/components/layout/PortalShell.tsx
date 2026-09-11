import { useState } from 'react';
import { Link, NavLink, Outlet } from 'react-router-dom';
import { LogOut, PanelLeftClose, PanelLeftOpen, type LucideIcon } from 'lucide-react';
import { ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/Button';
import { ThemeToggle } from '@/components/ui/ThemeToggle';

export interface PortalNavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

interface PortalShellProps {
  brand: string;
  brandTo: string;
  nav: PortalNavItem[];
  onLogout: () => void;
  topbarRight?: ReactNode;
}

const COLLAPSE_KEY = 'rosulo:sidebarCollapsed';

export function PortalShell({ brand, brandTo, nav, onLogout, topbarRight }: PortalShellProps) {
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(COLLAPSE_KEY) === '1');

  const toggleCollapsed = () => {
    setCollapsed((prev) => {
      localStorage.setItem(COLLAPSE_KEY, prev ? '0' : '1');
      return !prev;
    });
  };

  return (
    <div className="min-h-screen bg-bg">
      <header className="sticky top-0 z-30 border-b border-line bg-surface/80 backdrop-blur">
        <div className="flex h-14 items-center justify-between gap-4 px-4">
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleCollapsed}
              aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              className="hidden md:inline-flex"
            >
              {collapsed ? (
                <PanelLeftOpen className="h-4 w-4" aria-hidden="true" />
              ) : (
                <PanelLeftClose className="h-4 w-4" aria-hidden="true" />
              )}
            </Button>
            <Link to={brandTo} className="flex items-center gap-2 text-lg font-bold text-primary">
              <img src="/logo.svg" alt="" className="h-6 w-6" aria-hidden="true" />
              <span className="hidden sm:inline">{brand}</span>
            </Link>
          </div>
          <div className="flex items-center gap-1">
            {topbarRight}
            <ThemeToggle />
            <Button variant="ghost" size="sm" onClick={onLogout}>
              <LogOut className="h-4 w-4" aria-hidden="true" />
              <span className="hidden sm:inline">Log out</span>
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-7xl gap-6 p-4 lg:p-8">
        {/* Desktop sidebar */}
        <nav
          aria-label="Primary"
          className={cn(
            'sticky top-[4.5rem] hidden h-fit shrink-0 flex-col gap-1 self-start md:flex',
            collapsed ? 'w-16' : 'w-56'
          )}
        >
          <ul className="flex flex-col gap-1">
            {nav.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  title={collapsed ? item.label : undefined}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                      collapsed && 'justify-center px-2',
                      isActive
                        ? 'bg-brand-50 text-brand-700 dark:bg-primary/10 dark:text-brand-300'
                        : 'text-fg-muted hover:bg-surface-muted hover:text-fg'
                    )
                  }
                >
                  <item.icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                  {!collapsed && <span className="truncate">{item.label}</span>}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <main id="main-content" className="min-w-0 flex-1 pb-20 md:pb-0">
          <Outlet />
        </main>
      </div>

      {/* Mobile bottom navigation */}
      <nav
        aria-label="Main navigation"
        className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface md:hidden"
        style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
      >
        <ul className="grid grid-cols-5">
          {nav.slice(0, 5).map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    'flex flex-col items-center gap-1 px-1 py-2.5 text-[11px] font-medium transition-colors',
                    isActive ? 'text-primary' : 'text-fg-muted hover:text-fg'
                  )
                }
              >
                <item.icon className="h-5 w-5" aria-hidden="true" />
                <span className="truncate">{item.label}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}
