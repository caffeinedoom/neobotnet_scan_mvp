# 🚀 Deployment Workflows (MVP Setup)

## Current Setup (Development MVP)

**Active Workflows:**
- ✅ `deploy-backend-optimized.yml` → **"Deploy to AWS (Development)"**
  - Triggers: Any push to `dev` branch
  - Duration: ~1.5 minutes 
  - Handles: All changes (code + infrastructure)

**Disabled/Preserved Workflows:**
- 🚫 `deploy-backend.yml.disabled` - Legacy workflow (preserved for reference)

## MVP Philosophy

Following the **modular, minimal, and scalable** approach:
- ✅ **Minimal**: Single workflow for development
- ✅ **Reliable**: Proven optimized deployment
- ✅ **Simple**: No complex path filtering or multiple workflows

## Future Scaling (When Ready for Production)

**When moving to production, consider adding:**
1. **Production workflow** (manual trigger on `main` branch)
2. **Code-only fast deployment** (for quick fixes)
3. **Environment-specific configurations** (dev/staging/prod)

**For now:** Keep it simple, get the MVP working, iterate based on real needs.

## Usage

```bash
# Trigger deployment
git push origin dev

# Manual deployment
# Go to GitHub Actions → "Deploy to AWS (Development)" → "Run workflow"
```
