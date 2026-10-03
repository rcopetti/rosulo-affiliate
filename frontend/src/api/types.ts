export interface Tenant {
  id: string;
  name: string;
  logo_url?: string;
  allowed_domains?: string[];
}

// GET /affiliate/merchants keys linked merchants by tenant_id (the value sent
// as X-Tenant-Id), unlike auth responses that use the Tenant shape's `id`.
export interface LinkedMerchant {
  tenant_id: string;
  name: string;
  payout_eligibility?: { status: string };
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
  available_at?: string | null;
  created_at: string;
}

export interface PayoutPaymentConfirmation {
  /** ISO-8601 timestamp with an explicit offset; the browser-local
   * datetime-local value must be converted before submitting. */
  paid_at: string;
  transfer_reference: string;
}

export interface PayoutPayment {
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

export type PayoutStatus = 'pending_approval' | 'approved' | 'rejected' | 'paid';

export interface PayoutPayee {
  name: string;
  email: string;
  paypal_email?: string | null;
}

export interface PayoutCommissionDetail {
  commission_id: string;
  event_id: string;
  occurred_at?: string | null;
  good_date?: string | null;
  payment_sequence?: number | null;
  sale_amount?: number | null;
  sale_payment_record_id?: string | null;
  rate_percent?: number | null;
  gross_amount: number;
  withholding_amount: number;
  net_amount: number;
  currency: string;
  campaign_id?: string | null;
}

export type PayoutNotificationStatus = 'pending' | 'sending' | 'sent' | 'failed';

/** Delivery state of the payout-paid email, exposed on the payout detail so
 * merchants can spot and retry a failed send. */
export interface PayoutNotification {
  status: PayoutNotificationStatus;
  attempt_count: number;
  last_attempt_at?: string | null;
  sent_at?: string | null;
}

export interface Payout {
  id: string;
  affiliate_id: string;
  tenant_id?: string;
  requested_amount: number;
  approved_amount: number;
  withholding_total: number;
  paypal_fees: number;
  net_paid: number;
  currency: string;
  status: PayoutStatus;
  requested_at: string;
  approved_at?: string | null;
  paid_at?: string | null;
  affiliate?: PayoutPayee;
  payout_commissions?: PayoutCommissionDetail[];
  commission_count?: number;
  earliest_sale_at?: string | null;
  latest_sale_at?: string | null;
  total_sale_amount?: number | null;
  payout_payment?: PayoutPayment | null;
  payout_notification?: PayoutNotification | null;
  transitions?: PayoutTransition[];
}

// Sparse queue-row shape served by the admin dashboard; the full `Payout`
// also satisfies it so list endpoints can feed the same component.
export interface PayoutQueueItem {
  id: string;
  affiliate_id?: string;
  requested_amount: number;
  currency: string;
  status: PayoutStatus;
  requested_at: string | null;
  affiliate?: Pick<PayoutPayee, 'name'> | null;
}

export interface PayoutRequestPayload {
  currency: string;
  commission_ids?: string[];
}

// Row of an affiliate's payout history served by
// GET /admin/affiliates/{id}/payouts.
export interface AffiliatePayoutHistoryItem {
  id: string;
  status: PayoutStatus;
  currency: string;
  requested_amount: number;
  approved_amount: number;
  withholding_total: number;
  net_paid: number;
  requested_at: string;
  approved_at?: string | null;
  paid_at?: string | null;
  payment_reference?: string | null;
}

// Paid payout totals for a single currency; never summed across currencies.
export interface AffiliatePaidCurrencyTotals {
  currency: string;
  rolling_12_months: number;
  year_to_date: number;
}

export interface AffiliatePayoutHistory {
  items: AffiliatePayoutHistoryItem[];
  total: number;
  limit: number;
  offset: number;
  paid_totals_by_currency: AffiliatePaidCurrencyTotals[];
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
  sales_volume: { bucket: string; count: number }[];
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
  payout_queue: PayoutQueueItem[];
}
