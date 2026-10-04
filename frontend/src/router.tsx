import { createBrowserRouter, Navigate, Outlet, useLocation } from 'react-router-dom';
import { AppShell } from '@/components/layout/AppShell';
import { AffiliateLayout } from '@/components/layout/AffiliateLayout';
import { AdminLayout } from '@/components/layout/AdminLayout';
import { useAuthStore } from '@/store/auth';

function AffiliateAuthGuard() {
  const token = useAuthStore((s) => s.token);
  const tenantId = useAuthStore((s) => s.currentTenantId);
  const location = useLocation();
  // Preserve the internal path+query (e.g. a payout email deep link) so the
  // login/merchant-selection flow can return the user to it. The value is
  // only ever a location inside this app — the login side re-validates it
  // before navigating.
  const returnTo = encodeURIComponent(location.pathname + location.search);
  if (!token) return <Navigate to={`/login?returnTo=${returnTo}`} replace />;
  if (!tenantId) return <Navigate to={`/merchants?returnTo=${returnTo}`} replace />;
  return <Outlet />;
}

function AdminAuthGuard() {
  const token = localStorage.getItem('rosulo:adminToken');
  if (!token) return <Navigate to="/admin/login" replace />;
  return <Outlet />;
}

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      {
        index: true,
        lazy: async () => ({ Component: (await import('@/pages/LandingPage')).LandingPage }),
      },
      {
        path: 'login',
        lazy: async () => ({ Component: (await import('@/pages/LoginPage')).LoginPage }),
      },
      {
        path: 'register',
        lazy: async () => ({ Component: (await import('@/pages/RegisterPage')).RegisterPage }),
      },
      {
        path: 'forgot-password',
        lazy: async () => ({
          Component: (await import('@/pages/ForgotPasswordPage')).AffiliateForgotPasswordPage,
        }),
      },
      {
        path: 'merchants',
        lazy: async () => ({ Component: (await import('@/pages/affiliate/MerchantSelectPage')).MerchantSelectPage }),
      },
      {
        path: 'affiliate',
        element: <AffiliateAuthGuard />,
        children: [
          {
            element: <AffiliateLayout />,
            children: [
              { index: true, element: <Navigate to="/affiliate/dashboard" replace /> },
              {
                path: 'dashboard',
                lazy: async () => ({ Component: (await import('@/pages/affiliate/DashboardPage')).DashboardPage }),
              },
              {
                path: 'campaigns',
                lazy: async () => ({ Component: (await import('@/pages/affiliate/CampaignsPage')).CampaignsPage }),
              },
              {
                path: 'campaigns/new',
                lazy: async () => ({
                  Component: (await import('@/pages/affiliate/CampaignCreatePage')).CampaignCreatePage,
                }),
              },
              {
                path: 'campaigns/:id',
                lazy: async () => ({ Component: (await import('@/pages/affiliate/CampaignEditPage')).CampaignEditPage }),
              },
              {
                path: 'balance',
                lazy: async () => ({ Component: (await import('@/pages/affiliate/BalancePage')).BalancePage }),
              },
              {
                path: 'payouts',
                lazy: async () => ({ Component: (await import('@/pages/affiliate/PayoutsPage')).PayoutsPage }),
              },
              {
                path: 'payouts/request',
                lazy: async () => ({ Component: (await import('@/pages/affiliate/RequestPayoutPage')).RequestPayoutPage }),
              },
              {
                path: 'payouts/:id',
                lazy: async () => ({ Component: (await import('@/pages/affiliate/PayoutDetailPage')).PayoutDetailPage }),
              },
              {
                path: 'profile',
                lazy: async () => ({ Component: (await import('@/pages/affiliate/ProfilePage')).ProfilePage }),
              },
            ],
          },
        ],
      },
      {
        path: 'admin/login',
        lazy: async () => ({ Component: (await import('@/pages/admin/LoginPage')).AdminLoginPage }),
      },
      {
        path: 'admin/register',
        lazy: async () => ({ Component: (await import('@/pages/admin/RegisterPage')).AdminRegisterPage }),
      },
      {
        path: 'admin/forgot-password',
        lazy: async () => ({
          Component: (await import('@/pages/ForgotPasswordPage')).AdminForgotPasswordPage,
        }),
      },
      {
        path: 'admin',
        element: <AdminAuthGuard />,
        children: [
          {
            element: <AdminLayout />,
            children: [
              { index: true, element: <Navigate to="/admin/dashboard" replace /> },
              {
                path: 'dashboard',
                lazy: async () => ({ Component: (await import('@/pages/admin/DashboardPage')).AdminDashboardPage }),
              },
              {
                path: 'affiliates',
                lazy: async () => ({ Component: (await import('@/pages/admin/AffiliatesPage')).AffiliatesPage }),
              },
              {
                path: 'affiliates/new',
                lazy: async () => ({ Component: (await import('@/pages/admin/AffiliateCreatePage')).AffiliateCreatePage }),
              },
              {
                path: 'affiliates/:id',
                lazy: async () => ({ Component: (await import('@/pages/admin/AffiliateDetailPage')).AffiliateDetailPage }),
              },
              {
                path: 'affiliates/:id/contract',
                lazy: async () => ({ Component: (await import('@/pages/admin/ContractEditPage')).ContractEditPage }),
              },
              {
                path: 'payouts',
                lazy: async () => ({ Component: (await import('@/pages/admin/PayoutsPage')).AdminPayoutsPage }),
              },
              {
                path: 'events',
                lazy: async () => ({ Component: (await import('@/pages/admin/EventsPage')).EventsPage }),
              },
              {
                path: 'integration',
                lazy: async () => ({ Component: (await import('@/pages/admin/IntegrationPage')).IntegrationPage }),
              },
            ],
          },
        ],
      },
      { path: '*', element: <Navigate to="/login" replace /> },
    ],
  },
]);
