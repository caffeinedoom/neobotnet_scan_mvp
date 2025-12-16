# 🔐 Secure Cookie Authentication Implementation

**Document Created**: December 16, 2025  
**Last Updated**: December 16, 2025  
**Status**: 🟡 In Progress

---

## 📋 Project Overview

### Goal
Implement httpOnly cookie-based authentication for the web application to provide maximum XSS protection while maintaining API key support for programmatic access.

### Background
- Frontend was inconsistently using Bearer tokens and `credentials: 'include'`
- Backend only supported Bearer JWT and API keys
- Result: 401 errors on pages using cookie-based auth approach

### Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    TARGET (Secure + Consistent)             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Frontend                         Backend                   │
│  ────────                         ───────                   │
│  Supabase Login                                             │
│       │                                                     │
│       ▼                                                     │
│  Call POST /auth/session ──────►  Validate Supabase JWT    │
│  with Bearer token                      │                   │
│       │                                 ▼                   │
│       │                           Set httpOnly cookie       │
│       ▼                           (secure, SameSite=Lax)   │
│  Cookie stored by browser                                   │
│       │                                                     │
│       └──► All API calls ───────►  Accepts:                │
│            (credentials:include)   • httpOnly cookie ✓     │
│                                    • X-API-Key ✓           │
│                                                             │
│  Programmatic Access:                                       │
│  curl -H "X-API-Key: xxx" ──────►  API Key auth ✓          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔑 Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Cookie Content** | Store Supabase JWT in cookie | Simpler - no separate session management |
| **Cookie Settings** | `httpOnly`, `Secure`, `SameSite=Lax` | XSS protection + reasonable CSRF protection |
| **CSRF Strategy** | `SameSite=Lax` + check `Origin` header | Simpler than CSRF tokens, sufficient for API |
| **Token Refresh** | Frontend calls `/auth/session` after Supabase refresh | Keeps cookie in sync |
| **API Keys** | Keep existing `X-API-Key` support | For programmatic access |

---

## 📊 Phase Overview

| Phase | Name | Status | Notes |
|-------|------|--------|-------|
| 1 | Backend Cookie Support | ✅ Complete | Session endpoints, cookie validation |
| 2 | Frontend Cookie Integration | ✅ Complete | AuthContext, apiClient updates |
| 3 | Backend LEAN Fixes | 🟡 In Progress | Remove user_id filtering |
| 4 | Testing & Cleanup | ⬜ Not Started | End-to-end validation |

---

## ✅ Phase 1: Backend Cookie Support

### Tasks

- [x] **1.1** Create `/api/v1/auth/session` endpoint ✅ COMPLETED
  - POST: Validate Bearer JWT, set httpOnly cookie with token
  - DELETE: Clear cookie (logout)
  - GET: Return user info from cookie

- [x] **1.2** Update `get_current_user()` in `dependencies.py` ✅ COMPLETED
  - Add cookie extraction logic (check `neobotnet_session` cookie)
  - Parse JWT from cookie
  - Keep API key support
  - Keep Bearer token support (temporary)

- [x] **1.3** Add CORS cookie configuration in `main.py` ✅ ALREADY CONFIGURED
  - Allow credentials from frontend origin
  - Set `Access-Control-Allow-Credentials: true`

- [x] **1.4** Add cookie settings to `config.py` ✅ ALREADY CONFIGURED
  - Cookie name: `neobotnet_session`
  - Domain configuration
  - Secure flag, SameSite settings

### Files Modified
- `backend/app/api/v1/auth.py` - Added session endpoints (POST/GET/DELETE /auth/session)
- `backend/app/core/dependencies.py` - Updated to read `neobotnet_session` cookie
- `backend/app/core/config.py` - Cookie settings already existed ✓
- `backend/app/main.py` - CORS credentials already configured ✓

---

## ✅ Phase 2: Frontend Cookie Integration

### Tasks

- [x] **2.1** Update `AuthContext.tsx` ✅ COMPLETED
  - After Supabase auth success → POST to `/auth/session` (creates cookie)
  - On logout → DELETE `/auth/session` (clears cookie)
  - On token refresh → POST `/auth/session` (updates cookie)

- [x] **2.2** Update `apiClient` in `client.ts` ✅ COMPLETED
  - Added `withCredentials: true` to axios config
  - Kept Bearer token interceptor as fallback (both methods work)

- [x] **2.3** Fix raw `fetch()` calls to use `apiClient` ✅ COMPLETED
  - Fixed `subdomains/page.tsx` filter-options fetch

### Files Modified
- `frontend/src/contexts/AuthContext.tsx` - Added `createBackendSession()` call
- `frontend/src/lib/api/client.ts` - Added `withCredentials: true`
- `frontend/src/app/subdomains/page.tsx` - Replaced raw fetch with apiClient

---

## ✅ Phase 3: Backend LEAN Fixes

### Tasks

- [ ] **3.1** Remove user_id filtering from `http_probes.py`
- [ ] **3.2** Verify `dns-records/paginated` has no user_id filter
- [ ] **3.3** Verify `subdomains/paginated` has no user_id filter
- [ ] **3.4** Verify `filter-options` has no user_id filter

### Files to Modify
- `backend/app/api/v1/http_probes.py`
- `backend/app/api/v1/assets.py`
- `backend/app/services/asset_service.py`

---

## ✅ Phase 4: Testing & Cleanup

### Tasks

- [ ] **4.1** Test login → cookie set → API calls work
- [ ] **4.2** Test logout → cookie cleared
- [ ] **4.3** Test token refresh → cookie updated
- [ ] **4.4** Test API key access still works
- [ ] **4.5** Test all data pages (subdomains, dns, probes)
- [ ] **4.6** Deploy and verify in production

---

## 📝 Session Notes

### December 16, 2025 - Session 1
- Identified root cause: Frontend using `credentials: 'include'` but backend doesn't support cookies
- Decided on secure path: Implement httpOnly cookie support
- Created implementation plan with 4 phases
- ✅ Completed Phase 1: Backend Cookie Support
  - Added `/api/v1/auth/session` endpoints (POST, DELETE, GET)
  - Updated `dependencies.py` to read `neobotnet_session` cookie
  - Verified CORS and cookie settings already configured
- ✅ Completed Phase 2: Frontend Cookie Integration
  - Added `createBackendSession()` to AuthContext.tsx
  - Updated apiClient with `withCredentials: true`
  - Fixed subdomains/page.tsx to use apiClient
- 🟡 Starting Phase 3: Backend LEAN Fixes

---

## 🔗 Related Documents

- [LEAN Refactoring Plan](./REFACTOR_NEO_2025_12_14.md)
- [Architecture Overview](../proper/01-ARCHITECTURE-OVERVIEW.md)

