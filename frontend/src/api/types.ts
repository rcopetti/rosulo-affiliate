export interface Tenant {
  id: string;
  name: string;
  logo_url?: string;
  allowed_domains?: string[];
}

export interface AffiliateAccount {
  id: string;
  email: string;
  name: string;
  country?: string | null;
  state?: string | null;
  postal_code?: string | null;
  tax_id?: string | null;
  tax_status?: 'us_person' | 'non_us_person' | null;
  tax_form_type?: 'W-9' | 'W-8BEN' | 'W-8BEN-E' | null;
  paypal_email?: string | null;
  backup_withholding_required?: boolean;
  documents?: Document[];
}

export interface Document {
  id: string;
  type: string;
  url: string;
  status: 'pending' | 'approved' | 'rejected';
  uploaded_at: string;
}

export interface Affiliate {
  id: string;
  account_id: string;
  tenant_id: string;
  email: string;
  name: string;
  country?: string | null;
  state?: string | null;
  postal_code?: string | null;
  paypal_email?: string | null;
  kyc_approved_for_payout: boolean;
  enabled: boolean;
  contract?: Contract;
}

export interface Contract {
  id: string;
  affiliate_id: string;
  terms: Term[];
}

export interface Term {
  id: string;
  payment_sequence: string;
  commission_percent: number;
  effective_from?: string;
  effective_to?: string;
  minimum_threshold?: number;
}

export interface Campaign {
  id: string;
  affiliate_id: string;
  tenant_id: string;
  name: string;
  tracking_code: string;
  landing_url?: string;
  created_at: string;
}

export interface Commission {
  id: string;
  event_id: string;
  affiliate_id: string;
  campaign_id?: string;
  gross_amount: number;
  withholding_amount: number;
  net_amount: number;
  currency: string;
  status: 'pending' | 'available' | 'paid' | 'reversed';
  available_on?: string;
}

export interface Payout {
  id: string;
  affiliate_id: string;
  requested_amount: number;
  approved_amount: number;
  withholding_total: number;
  paypal_fees: number;
  net_paid: number;
  currency: string;
  status: 'requested' | 'pending_approval' | 'approved' | 'processing' | 'paid' | 'failed' | 'rejected';
  requested_at: string;
  approved_at?: string;
  paid_at?: string;
  paypal_batch_id?: string;
  commissions?: Commission[];
}

export interface Balance {
  earned: number;
  pending: number;
  available: number;
  paid: number;
  tax_retained: number;
  debt: number;
  currency: string;
}

export interface Event {
  id: string;
  event_id: string;
  type: 'click' | 'lead' | 'sale';
  tenant_id: string;
  campaign_id?: string;
  affiliate_id?: string;
  customer_id?: string;
  amount?: number;
  currency?: string;
  payment_sequence?: number;
  good_date?: string;
  referer?: string;
  page_url?: string;
  occurred_at: string;
}

export interface PaginatedEvents {
  items: Event[];
  total: number;
  skip: number;
  limit: number;
}

export interface Dashboard {
  lead_volume: { bucket: string; count: number }[];
  sales_by_sequence: { sequence: number; count: number; amount: number }[];
  balance: Balance;
}

export interface PendingInvite {
  id: string;
  tenant_id: string;
  tenant_name: string;
  token: string;
  expires_at: string | null;
}

export interface AdminDashboard {
  campaign_performance: { campaign_id: string; name: string; clicks: number; leads: number; sales: number }[];
  affiliates: Affiliate[];
  commission_liability: { period: string; gross: number; tax_retained: number }[];
  payout_queue: Payout[];
}
