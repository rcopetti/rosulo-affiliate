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
  tax_status?: 'us_person' | 'foreign_person' | null;
  tax_entity_type?: 'individual' | 'business' | null;
  business_name?: string | null;
  tax_form_type?: 'W-9' | 'W-8BEN' | 'W-8BEN-E' | null;
  paypal_email?: string | null;
  backup_withholding_required?: boolean;
}

export interface Document {
  id: string;
  type: string;
  url: string;
  status: 'pending' | 'approved' | 'rejected';
  uploaded_at: string;
}

export type PayoutEligibilityStatus = 'missing' | 'pending' | 'approved' | 'rejected';

export interface PayoutEligibility {
  eligible: boolean;
  status: PayoutEligibilityStatus;
  reason: string | null;
}

export interface AffiliateDocumentReview {
  status: 'approved' | 'rejected';
  reviewed_at: string;
  rejection_reason: string | null;
  reviewer: { id: string; name: string | null; email: string };
}

export interface AffiliateDocument {
  id: string;
  document_type: string;
  content_type: string;
  created_at: string;
  status: 'pending' | 'approved' | 'rejected';
  review_history: AffiliateDocumentReview[];
}

export interface AffiliateDocumentStatus {
  required_document_type: string;
  documents: AffiliateDocument[];
  payout_eligibility: PayoutEligibility;
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
  tax_status?: 'us_person' | 'foreign_person' | null;
  tax_entity_type?: 'individual' | 'business' | null;
  business_name?: string | null;
  tax_form_type?: 'W-9' | 'W-8BEN' | 'W-8BEN-E' | null;
  documents?: AffiliateDocument[];
  payout_eligibility: PayoutEligibility;
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
  campaign_id?: string;
  gross_amount: number;
  withholding_amount: number;
  net_amount: number;
  currency: string;
  status: 'pending' | 'available' | 'reserved' | 'paid' | 'reversed';
  available_on?: string | null;
  available_at?: string | null;
}

export interface PayoutPaymentConfirmation {
  payment_method: string;
  transfer_reference: string;
}

export interface PayoutPaymentRecord {
  id: string;
  payout_id: string;
  amount: number;
  currency: string;
  payment_method: string;
  transfer_reference: string;
  paid_at: string;
  recorded_by_tenant_user_id: string;
}

export interface PayoutTransition {
  id: string;
  sequence: number;
  from_status: string | null;
  to_status: string;
  actor_tenant_user_id: string | null;
  reason: string | null;
  created_at: string;
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
  payment_record?: PayoutPaymentRecord | null;
  transitions?: PayoutTransition[];
  commissions?: Commission[];
}

export interface PayoutRequestPayload {
  currency: string;
  commission_ids?: string[];
}

export interface CurrencyBalance {
  currency: string;
  earned: number;
  pending: number;
  available: number;
  paid: number;
  reserved: number;
  tax_retained: number;
  reversal_total: number;
}

export interface Balance {
  balances_by_currency: CurrencyBalance[];
  earned: number | null;
  pending: number | null;
  available: number | null;
  paid: number | null;
  reserved: number | null;
  reversed: number | null;
  tax_retained: number | null;
  reversal_total: number | null;
  debt: number | null;
  currency: string | null;
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
  commission_status?: 'currency_unsupported' | null;
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
  sales_by_sequence: { sequence: number; count: number; amount: number; currency: string }[];
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
  commission_liability: { period: string; gross: number; tax_retained: number; currency: string }[];
  payout_queue: Payout[];
}
