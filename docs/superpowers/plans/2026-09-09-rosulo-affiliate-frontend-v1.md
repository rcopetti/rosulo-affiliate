# Rosulo Affiliate v1 Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan package-by-package. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a responsive, accessible web frontend for the Rosulo Affiliate Service. The frontend serves two primary audiences: affiliates (self-service dashboard, campaigns, payouts) and tenant admins (affiliate/contract/payout management). It authenticates against the FastAPI backend and uses `X-Tenant-Id` for affiliate merchant selection.

**Architecture:** A TypeScript React single-page application (SPA) built with Vite. Client state and auth live in a minimal Zustand store. Server state is managed with TanStack Query (React Query). Forms use React Hook Form + Zod validation. Routing uses React Router. Styling uses Tailwind CSS with a design-token system. Layouts, pages, and feature modules are organized so multiple agents can work in parallel with minimal merge conflicts.

**Tech Stack:** TypeScript, React 18, Vite, React Router, TanStack Query, Zustand, React Hook Form, Zod, Tailwind CSS, Radix UI primitives, Recharts or Chart.js, Vitest + React Testing Library, Playwright for e2e.

---

## Reference

- Source spec: `docs/specs/2026-09-09-rosulo-affiliate-service-definition.md`
- Backend plan: `docs/superpowers/plans/2026-09-09-rosulo-affiliate-v1.md`

---

## Cross-Agent Contracts

Before any feature package begins, the following shared files must exist and be treated as contracts. They are created in **Package 1** and are read-only for downstream agents unless a cross-team change is approved.

| Contract | Purpose | Owner |
|----------|---------|-------|
| `src/api/client.ts` | Axios/HTTP client with auth header injection and `X-Tenant-Id` handling | Package 1 |
| `src/api/types.ts` | Auto-generated or hand-written API response/request types matching the FastAPI OpenAPI spec | Package 1 |
| `src/store/auth.ts` | Zustand store for account, token, and selected tenant | Package 1 + Package 2 |
| `src/lib/design-tokens.ts` | Tailwind config and CSS custom properties (colors, typography, spacing, breakpoints) | Package 1 |
| `src/components/ui/*` | Reusable unstyled/styled primitives (Button, Input, Select, Card, Table, Modal, Toast) | Package 1 |
| `src/lib/utils.ts` | cn() helper, currency formatting, date formatting, validation helpers | Package 1 |
| `src/router.tsx` | Top-level routes and protected route guards | Package 2 |

---

## File Structure

```
rosulo-affiliate-frontend/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
├── index.html
├── .env.example
├── public/
│   └── logo.svg
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── router.tsx
│   ├── api/
│   │   ├── client.ts
│   │   ├── types.ts
│   │   ├── auth.ts
│   │   ├── admin/
│   │   │   ├── affiliates.ts
│   │   │   ├── contracts.ts
│   │   │   ├── payouts.ts
│   │   │   ├── events.ts
│   │   │   └── dashboard.ts
│   │   ├── affiliate/
│   │   │   ├── merchants.ts
│   │   │   ├── profile.ts
│   │   │   ├── campaigns.ts
│   │   │   ├── balance.ts
│   │   │   ├── commissions.ts
│   │   │   ├── payouts.ts
│   │   │   └── dashboard.ts
│   │   └── public/
│   │       └── events.ts
│   ├── store/
│   │   └── auth.ts
│   ├── lib/
│   │   ├── design-tokens.ts
│   │   ├── utils.ts
│   │   ├── formatters.ts
│   │   └── validators.ts
│   ├── components/
│   │   ├── ui/
│   │   ├── layout/
│   │   │   ├── AppShell.tsx
│   │   │   ├── AdminLayout.tsx
│   │   │   └── AffiliateLayout.tsx
│   │   └── shared/
│   │       ├── CurrencyInput.tsx
│   │       ├── DatePicker.tsx
│   │       ├── TenantSelector.tsx
│   │       ├── KycStatusBadge.tsx
│   │       └── PayoutStatusBadge.tsx
│   ├── pages/
│   │   ├── LoginPage.tsx
│   │   ├── RegisterPage.tsx
│   │   ├── affiliate/
│   │   │   ├── MerchantSelectPage.tsx
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── CampaignsPage.tsx
│   │   │   ├── CampaignCreatePage.tsx
│   │   │   ├── CampaignEditPage.tsx
│   │   │   ├── BalancePage.tsx
│   │   │   ├── PayoutsPage.tsx
│   │   │   ├── RequestPayoutPage.tsx
│   │   │   └── ProfilePage.tsx
│   │   └── admin/
│   │       ├── LoginPage.tsx
│   │       ├── DashboardPage.tsx
│   │       ├── AffiliatesPage.tsx
│   │       ├── AffiliateCreatePage.tsx
│   │       ├── AffiliateDetailPage.tsx
│   │       ├── ContractEditPage.tsx
│   │       ├── PayoutsPage.tsx
│   │       └── EventsPage.tsx
│   ├── hooks/
│   │   ├── useCurrentTenant.ts
│   │   ├── useAffiliateAccount.ts
│   │   ├── useClickTracking.ts
│   │   └── useToast.ts
│   └── tests/
│       ├── setup.ts
│       └── ...
└── playwright/
    └── e2e/
        └── affiliate-flow.spec.ts
```

---

## Package 1 — Foundation Agent

**Responsibility:** Project scaffold, design system, shared UI primitives, and the API client contract.

**Files to create:**
- `package.json`
- `tsconfig.json`
- `vite.config.ts`
- `tailwind.config.js`
- `index.html`
- `.env.example`
- `src/main.tsx`
- `src/App.tsx`
- `src/api/client.ts`
- `src/api/types.ts` (seed with the most critical types from the OpenAPI spec)
- `src/lib/design-tokens.ts` or `tailwind.config.js` tokens
- `src/lib/utils.ts`
- `src/lib/formatters.ts`
- `src/components/ui/Button.tsx`
- `src/components/ui/Input.tsx`
- `src/components/ui/Select.tsx`
- `src/components/ui/Card.tsx`
- `src/components/ui/Table.tsx`
- `src/components/ui/Modal.tsx`
- `src/components/ui/Toast.tsx`
- `src/components/ui/Badge.tsx`

**Tasks:**

- [ ] Scaffold Vite + React + TypeScript project.
- [ ] Configure Tailwind, ESLint, Prettier, Vitest, React Testing Library.
- [ ] Implement `src/api/client.ts` with base URL, request/response interceptors, and `X-Tenant-Id` injection.
- [ ] Define design tokens in Tailwind config and `src/lib/design-tokens.ts`.
- [ ] Build the core UI primitives with accessibility attributes (ARIA, focus, keyboard).
- [ ] Add `src/lib/utils.ts` with `cn()`, currency, and date formatters.
- [ ] Seed `src/api/types.ts` with shared DTOs: `Tenant`, `AffiliateAccount`, `Affiliate`, `Campaign`, `Contract`, `Term`, `Payout`, `Commission`, `Balance`, `Event`.

**Acceptance:**
- `npm run dev` starts the dev server.
- `npm run test` runs an empty test suite without errors.
- All UI primitives render in Storybook or a simple `/style-guide` page.
- `src/api/client.ts` can make a request with `X-Tenant-Id` header.

---

## Package 2 — Auth & Tenant Selection Agent

**Responsibility:** Affiliate registration/login, global auth state, merchant selection, and routing guards.

**Files to create:**
- `src/store/auth.ts`
- `src/api/auth.ts`
- `src/router.tsx`
- `src/components/layout/AppShell.tsx`
- `src/components/layout/AffiliateLayout.tsx`
- `src/components/shared/TenantSelector.tsx`
- `src/pages/LoginPage.tsx`
- `src/pages/RegisterPage.tsx`
- `src/pages/affiliate/MerchantSelectPage.tsx`
- `src/hooks/useCurrentTenant.ts`
- `src/hooks/useAffiliateAccount.ts`

**Tasks:**

- [ ] Implement `src/store/auth.ts` with Zustand: `account`, `token`, `tenants`, `currentTenantId`, actions for `login`, `logout`, `setTenant`, `hydrate`.
- [ ] Implement `src/api/auth.ts` with `registerAffiliate` and `loginAffiliate`.
- [ ] Create `src/pages/LoginPage.tsx` and `src/pages/RegisterPage.tsx`.
- [ ] Create `src/pages/affiliate/MerchantSelectPage.tsx` after login; list `GET /v1/affiliate/merchants`.
- [ ] Add `TenantSelector.tsx` to the affiliate header for switching tenants.
- [ ] Create `src/router.tsx` with protected routes: `/login`, `/register`, `/merchants`, and `/affiliate/*`.
- [ ] Implement route guards that redirect unauthenticated users to `/login` and un-tenanted users to `/merchants`.

**Acceptance:**
- Affiliate can register, log in, see a list of merchants, and select one.
- After selecting, `X-Tenant-Id` is sent on all affiliate API calls.
- Switching merchants updates the displayed data.

---

## Package 3 — Affiliate Dashboard Agent

**Responsibility:** The main affiliate dashboard after merchant selection.

**Files to create:**
- `src/api/affiliate/dashboard.ts`
- `src/pages/affiliate/DashboardPage.tsx`
- `src/components/affiliate/StatsCards.tsx`
- `src/components/affiliate/LeadVolumeChart.tsx`
- `src/components/affiliate/SalesBySequenceChart.tsx`
- `src/components/affiliate/BalanceSummary.tsx`

**Tasks:**

- [ ] Implement `GET /v1/affiliate/dashboard` query hook.
- [ ] Build `DashboardPage.tsx` with the layout and widgets.
- [ ] Show lead volume by day/hour.
- [ ] Show sales grouped by payment sequence.
- [ ] Show balance summary: earned, pending, available, paid, tax retained, and debt.
- [ ] Add a campaign filter dropdown.

**Acceptance:**
- Dashboard loads for selected merchant.
- Charts respond to the campaign filter.
- Loading and error states are handled.

---

## Package 4 — Affiliate Campaigns & Payouts Agent

**Responsibility:** Campaign CRUD, balance/commissions page, payout request and history.

**Files to create:**
- `src/api/affiliate/campaigns.ts`
- `src/api/affiliate/balance.ts`
- `src/api/affiliate/commissions.ts`
- `src/api/affiliate/payouts.ts`
- `src/pages/affiliate/CampaignsPage.tsx`
- `src/pages/affiliate/CampaignCreatePage.tsx`
- `src/pages/affiliate/CampaignEditPage.tsx`
- `src/pages/affiliate/BalancePage.tsx`
- `src/pages/affiliate/PayoutsPage.tsx`
- `src/pages/affiliate/RequestPayoutPage.tsx`
- `src/components/affiliate/CampaignForm.tsx`
- `src/components/affiliate/CampaignsTable.tsx`
- `src/components/affiliate/CommissionsTable.tsx`
- `src/components/affiliate/PayoutsTable.tsx`

**Tasks:**

- [ ] Implement campaign list, create, edit, and detail views.
- [ ] Implement balance and commissions list with filtering.
- [ ] Implement payout request flow: show available balance, confirm request, show pending state.
- [ ] Implement payout history list.
- [ ] Block payout request if KYC is not approved (show KYC banner).

**Acceptance:**
- Affiliate can create and edit campaigns.
- Affiliate can view commissions and request a payout.
- Payout request page shows a confirmation with net amount after withholding.
- KYC unapproved state blocks the request with a clear message.

---

## Package 5 — Affiliate Profile Agent

**Responsibility:** Global profile, document upload, tax and PayPal information.

**Files to create:**
- `src/api/affiliate/profile.ts`
- `src/pages/affiliate/ProfilePage.tsx`
- `src/components/affiliate/ProfileForm.tsx`
- `src/components/affiliate/KycUploader.tsx`
- `src/components/affiliate/TaxStatusSelector.tsx`

**Tasks:**

- [ ] Implement `GET /v1/affiliate/profile` and `PATCH /v1/affiliate/profile`.
- [ ] Build profile form for name, country, state, tax ID, tax status, PayPal email.
- [ ] Build document uploader for W-9 / W-8BEN / proof of identity.
- [ ] Show KYC approval status per tenant.
- [ ] Add a "Tax information" section that explains why each form is needed.

**Acceptance:**
- Affiliate can update global profile and upload documents.
- Document upload shows upload progress and success/failure.
- Profile reflects KYC approval status for the selected merchant.

---

## Package 6 — Admin Auth & Layout Agent

**Responsibility:** Tenant admin login and the admin application shell.

**Files to create:**
- `src/components/layout/AdminLayout.tsx`
- `src/pages/admin/LoginPage.tsx`
- `src/api/admin/auth.ts` (or reuse tenant API key header)
- `src/store/admin.ts` (optional: keep admin token separate)
- `src/components/admin/AdminNav.tsx`

**Tasks:**

- [ ] Build admin login using API key or admin credentials.
- [ ] Create `AdminLayout.tsx` with navigation for Dashboard, Affiliates, Payouts, Events.
- [ ] Protect `/admin/*` routes behind admin auth.

**Acceptance:**
- Admin can log in and see the admin layout.
- Admin routes are not accessible to affiliates.

---

## Package 7 — Admin Dashboard Agent

**Responsibility:** Tenant admin dashboard with campaign performance, commission liability, and payout queue.

**Files to create:**
- `src/api/admin/dashboard.ts`
- `src/pages/admin/DashboardPage.tsx`
- `src/components/admin/CampaignPerformance.tsx`
- `src/components/admin/CommissionLiability.tsx`
- `src/components/admin/PayoutQueue.tsx`

**Tasks:**

- [ ] Implement `GET /v1/admin/dashboard` query.
- [ ] Show campaign performance: clicks, leads, conversion rate.
- [ ] Show affiliate list and approval status.
- [ ] Show commission liability by period.
- [ ] Show payout request queue with approve/reject actions.

**Acceptance:**
- Dashboard loads for the current tenant.
- Payout queue buttons trigger the approval/rejection API and refresh the queue.

---

## Package 8 — Admin Affiliate & Contract Management Agent

**Responsibility:** Create affiliates, view details, manage contracts and terms.

**Files to create:**
- `src/api/admin/affiliates.ts`
- `src/api/admin/contracts.ts`
- `src/pages/admin/AffiliatesPage.tsx`
- `src/pages/admin/AffiliateCreatePage.tsx`
- `src/pages/admin/AffiliateDetailPage.tsx`
- `src/pages/admin/ContractEditPage.tsx`
- `src/components/admin/AffiliateForm.tsx`
- `src/components/admin/ContractForm.tsx`
- `src/components/admin/TermEditor.tsx`

**Tasks:**

- [ ] Implement affiliate list and create (creates global account + per-tenant record).
- [ ] Implement affiliate detail view with KYC documents and approval toggle.
- [ ] Implement contract and term editor with payment sequences.
- [ ] Allow tenant admin to approve/reject KYC and enable/disable the affiliate for payouts.

**Acceptance:**
- Admin can create an affiliate with an email, contract, and terms.
- Admin can approve/reject KYC and edit the contract.

---

## Package 9 — Admin Events & Payouts Agent

**Responsibility:** Admin event stream, payout review, and detailed payout execution status.

**Files to create:**
- `src/api/admin/events.ts`
- `src/api/admin/payouts.ts`
- `src/pages/admin/EventsPage.tsx`
- `src/pages/admin/PayoutsPage.tsx`
- `src/components/admin/EventsTable.tsx`
- `src/components/admin/PayoutDetail.tsx`

**Tasks:**

- [ ] Implement `GET /v1/admin/events` with filters.
- [ ] Implement `GET /v1/admin/payouts` and `GET /v1/admin/payouts/{id}`.
- [ ] Show payout detail: gross, withholding, net, PayPal batch ID, status.
- [ ] Implement approve/reject actions on the payouts page.

**Acceptance:**
- Admin can list and filter events.
- Admin can review payout details and approve/reject.
- Payout list refreshes after action.

---

## Package 10 — Testing, Accessibility, and Performance Agent

**Responsibility:** End-to-end tests, component tests, accessibility audit, and production build setup.

**Files to create:**
- `vitest.config.ts`
- `src/tests/setup.ts`
- `src/tests/msw/handlers.ts` (Mock Service Worker for unit tests)
- `playwright/e2e/affiliate-flow.spec.ts`
- `playwright/e2e/admin-payout.spec.ts`

**Tasks:**

- [ ] Set up Vitest and React Testing Library.
- [ ] Set up Playwright and write two e2e flows:
  - Affiliate registers, logs in, selects a merchant, and views the dashboard.
  - Admin logs in, creates an affiliate, and approves a payout.
- [ ] Add component tests for the most reused UI primitives.
- [ ] Run an accessibility audit (Lighthouse or axe-core) and fix WCAG 2.1 AA issues.
- [ ] Verify responsive layout on 320px, 768px, and 1024px viewports.
- [ ] Set up the production build and confirm bundle size budget (<200KB initial JS).

**Acceptance:**
- `npm run test` and `npm run e2e` pass.
- Lighthouse Accessibility score is 95+.
- No layout breakage on mobile, tablet, and desktop viewports.
- `npm run build` produces a working `dist/`.

---

## Package Dependency Order

```
Package 1 (Foundation)
  │
  ├── Package 2 (Auth + Tenant Selection)
  │     ├── Package 3 (Affiliate Dashboard)
  │     ├── Package 4 (Campaigns + Payouts)
  │     └── Package 5 (Profile)
  │
  ├── Package 6 (Admin Auth + Layout)
  │     ├── Package 7 (Admin Dashboard)
  │     ├── Package 8 (Admin Affiliates + Contracts)
  │     └── Package 9 (Admin Events + Payouts)
  │
  └── Package 10 (Testing + A11y + Performance)
```

---

## Multi-Agent Execution Notes

- **Do not modify shared contracts without discussion.** If an agent needs a new shared type, add it to `src/api/types.ts` and notify the foundation agent.
- **No agent should add backend endpoints.** All API paths must match the backend OpenAPI spec.
- **Feature agents should only touch their own files.** Shared components may be extended but not renamed without coordination.
- **Use feature branches or subagent worktrees.** Each package can be built on its own branch and merged only after a smoke test against the Foundation Agent's scaffold.
- **Mock the backend for parallel development.** Use MSW or static JSON mocks so frontend agents are not blocked by backend completion.

---

## Self-Review

**Spec coverage:**
- Affiliate login and merchant selection: Packages 2.
- Affiliate dashboard: Package 3.
- Campaigns, balance, commissions, payout request: Package 4.
- Profile and KYC upload: Package 5.
- Admin login and layout: Package 6.
- Admin dashboard with campaign performance and payout queue: Package 7.
- Admin affiliate/contract management: Package 8.
- Admin events and payout review: Package 9.
- Responsive, accessible, tested: Package 10.

**Placeholder scan:** No TBD or TODO in package descriptions. Each package names the files, the API endpoints it consumes, and the acceptance criteria.

**Type consistency:** All packages consume `src/api/types.ts` and use the same `X-Tenant-Id` injection pattern from `src/api/client.ts`.

---

## Execution Options

Frontend plan complete and saved to `docs/superpowers/plans/2026-09-09-rosulo-affiliate-frontend-v1.md`.

**1. Subagent-Driven (recommended):** Dispatch a fresh subagent per package, starting with Package 1. Review shared contracts before downstream packages begin.

**2. Inline Execution:** Implement packages in this session, package by package.

Which approach do you want for the frontend?
