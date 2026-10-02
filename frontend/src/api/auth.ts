import { api } from './client';
import { AffiliateAccount, PendingInvite, Tenant } from './types';

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
  country: string;
  state?: string;
  tax_status?: string;
  tax_form_type?: string;
  paypal_email?: string;
}

export interface AcceptInviteRequest {
  token: string;
}

export interface AuthResponse {
  token: string;
  account: AffiliateAccount;
  tenants: Tenant[];
}

export async function loginAffiliate(data: LoginRequest): Promise<AuthResponse> {
  const res = await api.post<AuthResponse>('/auth/affiliate/login', data);
  return res.data;
}

export async function registerAffiliate(data: RegisterRequest): Promise<AuthResponse> {
  const res = await api.post<AuthResponse>('/auth/affiliate/register', data);
  return res.data;
}

export async function listInvites(): Promise<PendingInvite[]> {
  const res = await api.get<PendingInvite[]>('/auth/affiliate/invites');
  return res.data;
}

export async function acceptInvite(data: AcceptInviteRequest): Promise<AuthResponse> {
  const res = await api.post<AuthResponse>('/auth/affiliate/accept-invite', data);
  return res.data;
}

export async function fetchMerchants(): Promise<Tenant[]> {
  const res = await api.get<Tenant[]>('/affiliate/merchants');
  return res.data;
}

export async function selectMerchant(tenantId: string): Promise<void> {
  await api.post(`/affiliate/merchants/${tenantId}/select`);
}

/**
 * Validate an in-app deep link captured by the affiliate auth guard.
 *
 * Only affiliate payout detail links are honored, and only when the link's
 * `tenant_id` query param matches one of the tenants the authenticated
 * affiliate is linked to. External URLs, other paths, and foreign-tenant
 * links all return null so callers fall back to the default landing page.
 * The link never grants access on its own — the payout API still verifies
 * ownership for the current session and tenant context.
 */
export function safeAffiliateReturnTo(
  returnTo: string | null | undefined,
  tenantIds: string[]
): string | null {
  if (!returnTo || !returnTo.startsWith('/affiliate/payouts/')) return null;
  const tenantId = affiliateReturnTenantId(returnTo);
  if (!tenantId || !tenantIds.includes(tenantId)) return null;
  return returnTo;
}

/** Extract the `tenant_id` routing hint from a validated return path. */
export function affiliateReturnTenantId(returnTo: string): string | null {
  const queryStart = returnTo.indexOf('?');
  if (queryStart === -1) return null;
  return new URLSearchParams(returnTo.slice(queryStart + 1)).get('tenant_id');
}

export type ResetUserType = 'affiliate' | 'tenant';

export interface PasswordResetRequestInput {
  email: string;
  user_type: ResetUserType;
}

export interface PasswordResetVerifyInput extends PasswordResetRequestInput {
  code: string;
}

export interface PasswordResetConfirmInput extends PasswordResetRequestInput {
  reset_token: string;
  new_password: string;
}

export async function requestPasswordReset(data: PasswordResetRequestInput): Promise<void> {
  await api.post('/auth/password-reset/request', data);
}

export async function verifyPasswordResetCode(
  data: PasswordResetVerifyInput
): Promise<{ reset_token: string }> {
  const res = await api.post<{ reset_token: string }>('/auth/password-reset/verify', data);
  return res.data;
}

export async function confirmPasswordReset(data: PasswordResetConfirmInput): Promise<void> {
  await api.post('/auth/password-reset/confirm', data);
}
