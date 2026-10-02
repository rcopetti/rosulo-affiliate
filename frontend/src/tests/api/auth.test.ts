import { describe, expect, it } from 'vitest';
import { affiliateReturnTenantId, safeAffiliateReturnTo } from '@/api/auth';

const TENANTS = ['tenant-1', 'tenant-2'];
const VALID = '/affiliate/payouts/abc-123?tenant_id=tenant-1';

describe('safeAffiliateReturnTo', () => {
  it('accepts an affiliate payout deep link for a linked tenant', () => {
    expect(safeAffiliateReturnTo(VALID, TENANTS)).toBe(VALID);
  });

  it('rejects external URLs and protocol-relative links', () => {
    expect(
      safeAffiliateReturnTo(
        'https://evil.example.com/affiliate/payouts/abc?tenant_id=tenant-1',
        TENANTS
      )
    ).toBeNull();
    expect(
      safeAffiliateReturnTo(
        '//evil.example.com/affiliate/payouts/abc?tenant_id=tenant-1',
        TENANTS
      )
    ).toBeNull();
  });

  it('rejects internal paths outside the payout detail namespace', () => {
    expect(
      safeAffiliateReturnTo('/affiliate/dashboard?tenant_id=tenant-1', TENANTS)
    ).toBeNull();
    expect(
      safeAffiliateReturnTo('/admin/payouts/abc?tenant_id=tenant-1', TENANTS)
    ).toBeNull();
    expect(safeAffiliateReturnTo('/affiliate/payouts', TENANTS)).toBeNull();
  });

  it('rejects links without a tenant_id or for a foreign tenant', () => {
    expect(safeAffiliateReturnTo('/affiliate/payouts/abc-123', TENANTS)).toBeNull();
    expect(
      safeAffiliateReturnTo('/affiliate/payouts/abc-123?tenant_id=other', TENANTS)
    ).toBeNull();
  });

  it('rejects missing or empty returnTo values', () => {
    expect(safeAffiliateReturnTo(null, TENANTS)).toBeNull();
    expect(safeAffiliateReturnTo('', TENANTS)).toBeNull();
  });
});

describe('affiliateReturnTenantId', () => {
  it('extracts the tenant_id query param', () => {
    expect(affiliateReturnTenantId(VALID)).toBe('tenant-1');
    expect(affiliateReturnTenantId('/affiliate/payouts/abc')).toBeNull();
  });
});
