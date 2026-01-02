# Paywall & Rate Limiting Implementation

**Date:** January 1, 2026  
**Status:** 🟡 Planning  
**Target:** Ship MVP with monetization

---

## Overview

Implement a $13.37 one-time payment for full access, limited to the first 100 users. Free users get limited results.

---

## Pricing Model

| Tier | Price | Subdomains | DNS | Servers | URLs | API Calls/min |
|------|-------|------------|-----|---------|------|---------------|
| Free | $0 | ✅ Unlimited | ✅ Unlimited | ✅ Unlimited | 250 total | 30 |
| Paid | $13.37 (one-time) | ✅ Unlimited | ✅ Unlimited | ✅ Unlimited | ✅ Unlimited | 100 |

**Cap:** First 100 paid users only (creates urgency)

### Value Proposition
- **Free tier:** Full access to reconnaissance data (subdomains, DNS, servers)
- **Paid tier:** Unlock URLs — the crawled paths, parameters, and endpoints that matter for vuln hunting

---

## Implementation Phases

### Phase 1: Database Schema
**Time:** 30 min | **Status:** ✅ Complete

Uses existing `user_quotas` and `user_usage` tables (no separate profiles table exists).

```sql
-- Extend user_quotas with Stripe fields
ALTER TABLE user_quotas ADD COLUMN stripe_customer_id TEXT;
ALTER TABLE user_quotas ADD COLUMN stripe_payment_id TEXT;
ALTER TABLE user_quotas ADD COLUMN paid_at TIMESTAMPTZ;

-- Add URL tracking to user_usage
ALTER TABLE user_usage ADD COLUMN urls_viewed_count INTEGER DEFAULT 0;

-- Helper functions for 100 user cap
CREATE FUNCTION get_paid_user_count() ...
CREATE FUNCTION has_paid_spots_available(max_spots) ...
```

**Files:**
- [x] `backend/migrations/001_add_user_tiers.sql`

---

### Phase 2: Backend - URL Result Limiting
**Time:** 1 hour | **Status:** ⬜ Pending

Only the `/api/v1/urls` endpoint needs paywall logic:

```python
# backend/app/core/tier_limits.py
TIER_LIMITS = {
    "free": {
        "urls_limit": 250,        # Total URLs visible (not per-request)
        "rate_limit": "30/minute"
    },
    "paid": {
        "urls_limit": None,       # Unlimited
        "rate_limit": "100/minute"
    },
}
```

**Key behavior:**
- Free users can browse URLs but total results capped at 250
- Pagination works, but stops at 250 (e.g., page 3 of 25/page = last page)
- API returns `X-URLs-Limit: 250` and `X-URLs-Remaining: 47` headers
- When limit reached, return partial results + upgrade prompt in response

**Files to modify:**
- [ ] `backend/app/api/v1/urls.py` - Add 250 URL limit for free tier

**New files:**
- [ ] `backend/app/core/tier_limits.py` - Tier configuration
- [ ] `backend/app/dependencies/tier_check.py` - Get user tier helper

---

### Phase 3: Backend - Rate Limiting
**Time:** 1 hour | **Status:** ✅ Complete

Apply tiered rate limits to all authenticated endpoints:

| Tier | Rate Limit | Purpose |
|------|------------|---------|
| Free | 30/minute | Generous for exploration |
| Paid | 100/minute | Power user workflows |

Implemented via middleware that:
- Checks user tier from JWT/API key
- Applies rate limit per user or IP
- Returns X-RateLimit-* headers

**Files:**
- [x] `backend/app/main.py` - Global rate limit middleware
- [x] `backend/app/dependencies/rate_limit.py` - Tiered limiter utilities
- [x] `backend/app/middleware/rate_limit.py` - Rate limit middleware

---

### Phase 4: Stripe Integration
**Time:** 2-3 hours | **Status:** ⬜ Pending

#### 4a. Backend Stripe Endpoints

```
POST /api/v1/billing/checkout    → Create Stripe Checkout session
POST /api/v1/billing/webhook     → Handle payment success
GET  /api/v1/billing/status      → Check user's payment status
```

**Files:**
- [ ] `backend/app/api/v1/billing.py` - Stripe endpoints
- [ ] `backend/app/schemas/billing.py` - Pydantic models
- [ ] `backend/requirements.txt` - Add `stripe`

#### 4b. Stripe Dashboard Setup

- [ ] Create Stripe account (if not exists)
- [ ] Create product: "neobotnet Full Access"
- [ ] Create price: $13.37 one-time
- [ ] Set up webhook endpoint
- [ ] Get API keys (test + live)

#### 4c. Environment Variables

```bash
STRIPE_SECRET_KEY=sk_live_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
STRIPE_PRICE_ID=price_xxx
```

---

### Phase 5: Frontend - Upgrade Flow
**Time:** 2 hours | **Status:** ✅ Complete

#### 5a. New Pages

- [x] `/upgrade` - Pricing page with Stripe checkout button
- [x] `/upgrade/success` - Post-payment confirmation with confetti
- [x] `/upgrade/cancel` - Payment cancelled

#### 5b. UI Components

- [x] Upgrade CTA button in header (for free users)
- [x] "X of 100 spots remaining" badge on upgrade page
- [x] URLs page: Show limit banner when approaching/at 250 limit
- [x] URLs page: "Upgrade to unlock all URLs" prompt

#### 5c. URLs Page Specific

The `/urls` page is the only page with paywall UI:

```
┌─────────────────────────────────────────────────────────┐
│  🔓 You've viewed 250 of 47,832 URLs                    │
│                                                         │
│  Upgrade for $13.37 to unlock all URLs                  │
│  [Upgrade Now]                                          │
│                                                         │
│  ⚡ Only 73 spots remaining at this price               │
└─────────────────────────────────────────────────────────┘
```

**Files:**
- [ ] `frontend/src/app/upgrade/page.tsx`
- [ ] `frontend/src/app/upgrade/success/page.tsx`
- [ ] `frontend/src/app/upgrade/cancel/page.tsx`
- [ ] `frontend/src/app/urls/page.tsx` - Add limit UI
- [ ] `frontend/src/components/UpgradeCTA.tsx`
- [ ] `frontend/src/components/URLLimitBanner.tsx`

---

### Phase 6: Testing
**Time:** 1-2 hours | **Status:** ⬜ Pending

- [ ] Test Stripe checkout flow (test mode)
- [ ] Verify webhook updates user tier
- [ ] Verify result limits enforced
- [ ] Verify rate limits enforced
- [ ] Test 100 user cap logic
- [ ] Test free → paid upgrade flow

---

## File Checklist

### Backend (New)
```
backend/
├── app/
│   ├── api/v1/
│   │   └── billing.py          # Stripe endpoints
│   ├── core/
│   │   └── tier_limits.py      # Tier configuration
│   ├── dependencies/
│   │   ├── rate_limit.py       # Tiered rate limiter
│   │   └── tier_check.py       # Get user tier helper
│   └── schemas/
│       └── billing.py          # Billing schemas
└── migrations/
    └── 001_add_user_tiers.sql  # DB migration
```

### Backend (Modify)
```
backend/
├── app/
│   ├── api/v1/
│   │   └── urls.py             # Add 250 URL limit for free tier
│   └── main.py                 # Register billing router, global rate limits
└── requirements.txt            # Add stripe
```

### Frontend (New)
```
frontend/src/
├── app/
│   └── upgrade/
│       ├── page.tsx            # Pricing page
│       ├── success/page.tsx    # Success page
│       └── cancel/page.tsx     # Cancel page
├── components/
│   ├── UpgradeCTA.tsx          # Upgrade button (header)
│   └── URLLimitBanner.tsx      # URLs page limit banner
└── lib/api/
    └── billing.ts              # Billing API client
```

### Frontend (Modify)
```
frontend/src/
├── app/
│   └── urls/page.tsx           # Show limit UI (only page with paywall)
└── components/
    └── Header.tsx              # Add upgrade CTA for free users
```

---

## Environment Variables Required

### Backend (.env)
```bash
# Existing
SUPABASE_URL=xxx
SUPABASE_SERVICE_ROLE_KEY=xxx

# New - Stripe
STRIPE_SECRET_KEY=sk_live_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
STRIPE_PRICE_ID=price_xxx
```

### Frontend (.env.local)
```bash
# Existing
NEXT_PUBLIC_API_URL=xxx

# New - Stripe (public key for checkout)
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_live_xxx
```

---

## Success Criteria

- [ ] Subdomains, DNS, Servers: Fully free, no limits
- [ ] URLs: Free users limited to 250 total results
- [ ] Free users rate limited to 30 requests/minute
- [ ] Paid users have unlimited URL results
- [ ] Paid users rate limited to 100 requests/minute
- [ ] Stripe checkout works end-to-end
- [ ] Webhook properly upgrades user tier
- [ ] 100 paid user cap is enforced
- [ ] "Spots remaining" counter is accurate
- [ ] URLs page shows upgrade prompt at limit
- [ ] All existing functionality still works

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Webhook failure | Implement retry logic, log all events |
| User pays but not upgraded | Manual override endpoint for admin |
| Rate limit bypass | Enforce at API gateway level (CloudFront) |
| Refund handling | Stripe handles, webhook downgrades tier |

---

## Timeline

| Day | Tasks | Hours |
|-----|-------|-------|
| 1 | Phase 1: Schema migration | 0.5h |
| 1 | Phase 2: URL limit (single endpoint) | 1h |
| 1 | Phase 3: Rate limiting | 1h |
| 1 | Phase 4: Stripe backend | 2h |
| 1 | Phase 5: Frontend upgrade flow | 2h |
| 1 | Phase 6: Testing | 1h |
| **Total** | | **~7.5h** |

*Reduced from 9h due to simpler paywall model (URLs only)*

---

## Notes

- Using Stripe Checkout (hosted) for fastest implementation
- One-time payment = no subscription complexity
- 100 user cap creates scarcity/urgency
- Can always raise cap or add tiers later
- Keep it simple for MVP
- **Strategic:** Free recon data (subs/dns/servers) hooks users, URLs are the paywall
- URLs contain the real value: crawled paths, parameters, endpoints for vuln hunting

---

## Approval

- [ ] **Schema approved**
- [ ] **Stripe product/price created**
- [ ] **Ready to implement**

---

*Once approved, implementation begins with Phase 1.*
