# Paywall & Rate Limiting Implementation

**Date:** January 1, 2026  
**Status:** 🟡 Planning  
**Target:** Ship MVP with monetization

---

## Overview

Implement a $13.37 one-time payment for full access, limited to the first 100 users. Free users get limited results.

---

## Pricing Model

| Tier | Price | Result Limit | API Calls/min |
|------|-------|--------------|---------------|
| Free | $0 | 25 per request | 10 |
| Paid | $13.37 (one-time) | Unlimited | 100 |

**Cap:** First 100 paid users only (creates urgency)

---

## Implementation Phases

### Phase 1: Database Schema
**Time:** 30 min | **Status:** ⬜ Pending

```sql
-- Add to profiles table
ALTER TABLE profiles ADD COLUMN tier TEXT DEFAULT 'free' CHECK (tier IN ('free', 'paid'));
ALTER TABLE profiles ADD COLUMN paid_at TIMESTAMPTZ;
ALTER TABLE profiles ADD COLUMN stripe_customer_id TEXT;

-- Track paid user count
CREATE OR REPLACE FUNCTION get_paid_user_count() 
RETURNS INTEGER AS $$
  SELECT COUNT(*) FROM profiles WHERE tier = 'paid';
$$ LANGUAGE SQL;
```

**Files:**
- [ ] `backend/migrations/001_add_user_tiers.sql`

---

### Phase 2: Backend - Result Limiting
**Time:** 2 hours | **Status:** ⬜ Pending

Enforce limits at API level:

```python
# backend/app/core/tier_limits.py
TIER_LIMITS = {
    "free": {"result_limit": 25, "rate_limit": "10/minute"},
    "paid": {"result_limit": None, "rate_limit": "100/minute"},
}
```

**Files to modify:**
- [ ] `backend/app/api/v1/subdomains.py` - Add limit enforcement
- [ ] `backend/app/api/v1/dns.py` - Add limit enforcement
- [ ] `backend/app/api/v1/http_probes.py` - Add limit enforcement
- [ ] `backend/app/api/v1/urls.py` - Add limit enforcement
- [ ] `backend/app/api/v1/programs.py` - Add limit enforcement

**New files:**
- [ ] `backend/app/core/tier_limits.py` - Tier configuration
- [ ] `backend/app/dependencies/rate_limit.py` - Tiered rate limiter

---

### Phase 3: Backend - Rate Limiting
**Time:** 1 hour | **Status:** ⬜ Pending

Extend `slowapi` to all authenticated endpoints with tiered limits:

```python
def get_rate_limit_key(request: Request) -> str:
    user = get_current_user(request)
    tier = user.tier if user else "free"
    return f"{tier}:{get_remote_address(request)}"
```

**Files:**
- [ ] `backend/app/main.py` - Global rate limit handler
- [ ] `backend/app/dependencies/rate_limit.py` - Tiered limiter

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
**Time:** 2 hours | **Status:** ⬜ Pending

#### 5a. New Pages

- [ ] `/upgrade` - Pricing page with Stripe checkout button
- [ ] `/upgrade/success` - Post-payment confirmation
- [ ] `/upgrade/cancel` - Payment cancelled

#### 5b. UI Components

- [ ] Upgrade CTA button in header (for free users)
- [ ] "X of 100 spots remaining" badge
- [ ] Blur overlay on results beyond limit
- [ ] "Upgrade to see all results" prompt

**Files:**
- [ ] `frontend/src/app/upgrade/page.tsx`
- [ ] `frontend/src/app/upgrade/success/page.tsx`
- [ ] `frontend/src/app/upgrade/cancel/page.tsx`
- [ ] `frontend/src/components/UpgradeCTA.tsx`
- [ ] `frontend/src/components/ResultLimit.tsx`

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
│   │   └── rate_limit.py       # Tiered rate limiter
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
│   │   ├── subdomains.py       # Add limits
│   │   ├── dns.py              # Add limits
│   │   ├── http_probes.py      # Add limits
│   │   ├── urls.py             # Add limits
│   │   └── programs.py         # Add limits
│   └── main.py                 # Register billing router
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
│   ├── UpgradeCTA.tsx          # Upgrade button
│   └── ResultLimit.tsx         # Limit enforcement UI
└── lib/api/
    └── billing.ts              # Billing API client
```

### Frontend (Modify)
```
frontend/src/
├── app/
│   ├── subdomains/page.tsx     # Show limit UI
│   ├── dns/page.tsx            # Show limit UI
│   ├── probes/page.tsx         # Show limit UI
│   └── urls/page.tsx           # Show limit UI
└── components/
    └── Header.tsx              # Add upgrade CTA
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

- [ ] Free users limited to 25 results per request
- [ ] Free users rate limited to 10 requests/minute
- [ ] Paid users have unlimited results
- [ ] Paid users rate limited to 100 requests/minute
- [ ] Stripe checkout works end-to-end
- [ ] Webhook properly upgrades user tier
- [ ] 100 user cap is enforced
- [ ] "Spots remaining" counter is accurate
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
| 1 | Phase 1-2: Schema + Result limits | 2.5h |
| 1 | Phase 3: Rate limiting | 1h |
| 1 | Phase 4: Stripe backend | 2h |
| 2 | Phase 5: Frontend upgrade flow | 2h |
| 2 | Phase 6: Testing | 1.5h |
| **Total** | | **~9h** |

---

## Notes

- Using Stripe Checkout (hosted) for fastest implementation
- One-time payment = no subscription complexity
- 100 user cap creates scarcity/urgency
- Can always raise cap or add tiers later
- Keep it simple for MVP

---

## Approval

- [ ] **Schema approved**
- [ ] **Stripe product/price created**
- [ ] **Ready to implement**

---

*Once approved, implementation begins with Phase 1.*
