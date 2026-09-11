import { createBrowserRouter, Navigate, Outlet } from 'react-router-dom';
import { AppShell } from '@/components/layout/AppShell';
import { AffiliateLayout } from '@/components/layout/AffiliateLayout';
import { AdminLayout } from '@/components/layout/AdminLayout';
import { LandingPage } from '@/pages/LandingPage';
import { LoginPage } from '@/pages/LoginPage';
import { RegisterPage } from '@/pages/RegisterPage';
import { AdminRegisterPage } from '@/pages/admin/RegisterPage';
import { IntegrationPage } from '@/pages/admin/IntegrationPage';
import { MerchantSelectPage } from '@/pages/affiliate/MerchantSelectPage';
import { DashboardPage } from '@/pages/affiliate/DashboardPage';
import { CampaignsPage } from '@/pages/affiliate/CampaignsPage';
import { CampaignCreatePage } from '@/pages/affiliate/CampaignCreatePage';
import { CampaignEditPage } from '@/pages/affiliate/CampaignEditPage';
import { BalancePage } from '@/pages/affiliate/BalancePage';
import { PayoutsPage } from '@/pages/affiliate/PayoutsPage';
import { RequestPayoutPage } from '@/pages/affiliate/RequestPayoutPage';
import { ProfilePage } from '@/pages/affiliate/ProfilePage';
import { AdminLoginPage } from '@/pages/admin/LoginPage';
import { AdminDashboardPage } from '@/pages/admin/DashboardPage';
import { AffiliatesPage } from '@/pages/admin/AffiliatesPage';
import { AffiliateCreatePage } from '@/pages/admin/AffiliateCreatePage';
import { AffiliateDetailPage } from '@/pages/admin/AffiliateDetailPage';
import { ContractEditPage } from '@/pages/admin/ContractEditPage';
import { AdminPayoutsPage } from '@/pages/admin/PayoutsPage';
import { EventsPage } from '@/pages/admin/EventsPage';
import { useAuthStore } from '@/store/auth';

function AffiliateAuthGuard() {
  const token = useAuthStore((s) => s.token);
  const tenantId = useAuthStore((s) => s.currentTenantId);
  if (!token) return <Navigate to="/login" replace />;
  if (!tenantId) return <Navigate to="/merchants" replace />;
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
      { index: true, element: <LandingPage /> },
      { path: 'login', element: <LoginPage /> },
      { path: 'register', element: <RegisterPage /> },
      { path: 'merchants', element: <MerchantSelectPage /> },
      {
        path: 'affiliate',
        element: <AffiliateAuthGuard />,
        children: [
          {
            element: <AffiliateLayout />,
            children: [
              { index: true, element: <Navigate to="/affiliate/dashboard" replace /> },
              { path: 'dashboard', element: <DashboardPage /> },
              { path: 'campaigns', element: <CampaignsPage /> },
              { path: 'campaigns/new', element: <CampaignCreatePage /> },
              { path: 'campaigns/:id', element: <CampaignEditPage /> },
              { path: 'balance', element: <BalancePage /> },
              { path: 'payouts', element: <PayoutsPage /> },
              { path: 'payouts/request', element: <RequestPayoutPage /> },
              { path: 'profile', element: <ProfilePage /> },
            ],
          },
        ],
      },
      { path: 'admin/login', element: <AdminLoginPage /> },
      { path: 'admin/register', element: <AdminRegisterPage /> },
      {
        path: 'admin',
        element: <AdminAuthGuard />,
        children: [
          {
            element: <AdminLayout />,
            children: [
              { index: true, element: <Navigate to="/admin/dashboard" replace /> },
              { path: 'dashboard', element: <AdminDashboardPage /> },
              { path: 'affiliates', element: <AffiliatesPage /> },
              { path: 'affiliates/new', element: <AffiliateCreatePage /> },
              { path: 'affiliates/:id', element: <AffiliateDetailPage /> },
              { path: 'affiliates/:id/contract', element: <ContractEditPage /> },
              { path: 'payouts', element: <AdminPayoutsPage /> },
              { path: 'events', element: <EventsPage /> },
              { path: 'integration', element: <IntegrationPage /> },
            ],
          },
        ],
      },
      { path: '*', element: <Navigate to="/login" replace /> },
    ],
  },
]);
