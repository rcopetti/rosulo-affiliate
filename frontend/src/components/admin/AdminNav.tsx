import { LayoutDashboard, Users, CreditCard, Activity } from 'lucide-react';

export function AdminNav() {
  return (
    <nav className="flex items-center gap-4 text-sm text-slate-600">
      <a href="/admin/dashboard" className="flex items-center gap-1 hover:text-slate-900">
        <LayoutDashboard className="h-4 w-4" /> Dashboard
      </a>
      <a href="/admin/affiliates" className="flex items-center gap-1 hover:text-slate-900">
        <Users className="h-4 w-4" /> Affiliates
      </a>
      <a href="/admin/payouts" className="flex items-center gap-1 hover:text-slate-900">
        <CreditCard className="h-4 w-4" /> Payouts
      </a>
      <a href="/admin/events" className="flex items-center gap-1 hover:text-slate-900">
        <Activity className="h-4 w-4" /> Events
      </a>
    </nav>
  );
}
