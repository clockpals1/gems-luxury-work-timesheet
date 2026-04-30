# Migration Changelog

## v2 — Supabase + Render re-engineering (current)

The platform was re-engineered to remove every Emergent / Cloudflare R2 /
MongoDB dependency. The current target stack is:

- Frontend: **Cloudflare Pages** (unchanged)
- Backend: **Render** (Docker, FastAPI / Python 3.11)
- Database: **Supabase Postgres** (replaces MongoDB Atlas)
- Storage: **Supabase Storage** (replaces Cloudflare R2)
- AI text: **Anthropic Claude** via official `anthropic` SDK
- AI images: **Google Gemini** via official `google-genai` SDK

### Key code changes

- `backend/db.py` — new asyncpg + JSONB adapter exposing the small
  Mongo-compatible API (`find_one`, `find().sort().to_list()`,
  `insert_one`, `update_one` with `$set`/`$inc`/`upsert`,
  `count_documents`). Each Mongo "collection" is stored as a row in a
  `gl_<collection>` JSONB table; the schema is auto-created on startup
  and is also captured in `backend/sql/schema.sql`.
- `backend/server.py` — swapped `motor.motor_asyncio.AsyncIOMotorClient`
  for the new adapter. All other handler logic is unchanged. Added a
  `/health` endpoint for Render.
- `backend/storage.py` — rewritten to talk to the Supabase Storage REST
  API directly via `httpx`. The Cloudflare R2 binding (which only worked
  inside Workers) is gone.
- `backend/ai_service.py` — Emergent integration removed. Now uses the
  official Anthropic SDK for product-draft generation and the official
  `google-genai` SDK for image enhance / alternate views.
- `backend/requirements.txt` — pruned to the minimum: FastAPI, asyncpg,
  httpx, anthropic, google-genai, apscheduler, rapidfuzz, bcrypt, PyJWT.
  `motor`, `pymongo`, `boto3`, `emergentintegrations` are gone.
- `backend/Dockerfile` — uses `$PORT` for Render compatibility.
- `render.yaml` — Render Blueprint at the repo root provisions the
  backend service and required env vars.
- `.github/workflows/deploy-backend.yml` — replaced the GHCR + Cloudflare
  Run pipeline with a simple Render deploy hook trigger.
- `.github/workflows/deploy-frontend.yml` — re-enabled, builds the React
  app and deploys to Cloudflare Pages with the official
  `cloudflare/wrangler-action`.
- `frontend/public/_redirects` — SPA fallback for Pages.
- `frontend/package.json` — removed the `@emergentbase/visual-edits`
  devDependency that pointed at a private tarball URL.
- Removed dead Workers shims: `backend/worker.py`,
  `backend/scheduled_worker.py`, `backend/wrangler.toml`.

### Required GitHub secrets

| Secret | Purpose |
| --- | --- |
| `RENDER_DEPLOY_HOOK_URL` | Triggers Render redeploy on backend push |
| `CLOUDFLARE_API_TOKEN` | Pages: Edit token |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account ID |
| `REACT_APP_BACKEND_URL` | Public Render backend URL baked into build |

---

## v1 — Hybrid Cloudflare architecture (historical)

Migrated Gems & Luxury internal staff platform to a hybrid Cloudflare architecture:
- Frontend: Cloudflare Pages
- Storage: Cloudflare R2
- Backend: Container-based platform (Railway/Render/Cloudflare Run)
- Database: MongoDB Atlas (unchanged)

## Changes Made

### Phase 1: Frontend to Cloudflare Pages

**Files Created:**
- `.github/workflows/deploy-frontend.yml` - GitHub Actions workflow for frontend deployment
- `frontend/.env.example` - Environment variables template

**Changes:**
- Frontend now builds and deploys to Cloudflare Pages via GitHub Actions
- Environment variable `REACT_APP_BACKEND_URL` for API configuration

### Phase 2: Storage to Cloudflare R2

**Files Created:**
- `backend/wrangler.toml` - Cloudflare Workers configuration with R2 bucket binding
- `backend/.env.example` - Backend environment variables template

**Files Modified:**
- `backend/storage.py` - Complete rewrite to use Cloudflare R2 bucket bindings
  - Removed Emergent HTTP API integration
  - Added R2 bucket initialization
  - Updated `put_object()` and `get_object()` for R2
- `backend/requirements.txt` - Removed AWS dependencies
  - Removed: boto3, botocore, s3transfer, s5cmd
  - Removed: APScheduler (scheduled tasks moved to container)
  - Removed: reportlab (PDF generation moved to client-side)

**Storage Changes:**
- Storage path format unchanged: `{APP_NAME}/uploads/{user_id}/{uuid}.{ext}`
- R2 bucket binding: `R2_BUCKET` in wrangler.toml
- Bucket name: `gems-luxury-storage` (create in Cloudflare Dashboard)

### Phase 3: Backend CI/CD (Container-Based)

**Files Created:**
- `backend/Dockerfile` - Docker container configuration for backend
- `.github/workflows/deploy-backend.yml` - GitHub Actions for backend deployment
- `backend/worker.py` - Cloudflare Workers entry point (for future Workers migration)
- `backend/scheduled_worker.py` - Scheduled task handler for Cron Triggers

**Changes:**
- Backend now deploys via Docker to container platform
- GitHub Actions builds and pushes Docker image to GHCR
- Deployment supports Railway, Render, or Cloudflare Run
- Worker files created for future full Workers migration

### Phase 4: PDF Generation Migration

**Files Modified:**
- `backend/requirements.txt` - Removed reportlab dependency
- `backend/server.py` - Replaced PDF endpoint with JSON data endpoint
  - Endpoint: `/admin/reports/timesheet` now returns JSON
  - Removed reportlab imports and PDF generation logic
  - Returns structured data for client-side PDF generation
- `frontend/package.json` - Added jspdf dependency

**Changes:**
- PDF generation moved from server-side (reportlab) to client-side (jspdf)
- Backend provides JSON data, frontend renders PDF
- Removes filesystem dependencies
- Improves UX with client-side preview

### Phase 5: Documentation

**Files Modified:**
- `README.md` - Complete rewrite with Cloudflare architecture documentation

**Added:**
- Architecture overview and rationale
- Local development setup instructions
- Cloudflare setup guide (R2 bucket, wrangler, GitHub secrets)
- Deployment instructions for Pages and container platforms
- Storage migration guide
- PDF generation changes
- Troubleshooting section
- Project structure documentation

## Architecture Decisions

### Why Hybrid Instead of Full Workers?

Critical incompatibilities identified with Cloudflare Workers Python runtime (still in beta):
1. **APScheduler** - Requires persistent processes, Workers are stateless
2. **MongoDB connection pooling** - Current pattern incompatible with Workers
3. **reportlab** - Has filesystem dependencies, Workers has no filesystem
4. **emergentintegrations** - Unknown compatibility with Workers V8 isolate

### Hybrid Approach Benefits

- Frontend on Cloudflare Pages: Global CDN, instant deployments, free tier
- Storage on Cloudflare R2: S3-compatible, cost-effective, global distribution
- Backend on containers: Stable runtime, full Python compatibility, predictable performance
- MongoDB Atlas unchanged: No data migration needed, proven scalability

## Migration Steps for Deployment

### 1. Cloudflare Setup

```bash
# Create R2 bucket
# Go to Cloudflare Dashboard → R2 → Create Bucket
# Name: gems-luxury-storage

# Install wrangler
npm install -g wrangler
wrangler login
```

### 2. GitHub Secrets Configuration

Add these secrets to your GitHub repository:

**Cloudflare:**
- `CLOUDFLARE_ACCOUNT_ID` - From Cloudflare dashboard
- `CLOUDFLARE_API_TOKEN` - Create in Cloudflare → My Profile → API Tokens

**Backend:**
- `MONGO_URL` - MongoDB connection string
- `DB_NAME` - Database name
- `JWT_SECRET` - JWT signing key
- `EMERGENT_LLM_KEY` - Emergent API key

**Frontend:**
- `REACT_APP_BACKEND_URL` - Set in Cloudflare Pages project settings

### 3. Container Platform Setup

Choose one platform and configure:

**Railway:**
- Create project, connect GitHub repo
- Set environment variables from backend/.env.example
- Deploy

**Render:**
- Create Web Service, connect GitHub repo
- Set environment variables
- Deploy

**Cloudflare Run:**
- Uncomment Cloudflare Run section in `.github/workflows/deploy-backend.yml`
- Add service configuration
- Deploy

### 4. Storage Migration (Existing Images)

If you have existing images in Emergent storage:

1. Export images from Emergent storage
2. Use migration script to upload to R2
3. Update MongoDB `image_assets` collection:
```javascript
db.image_assets.updateMany(
  { storage_path: { $exists: true } },
  { $set: { storage_path: <new R2 path> } }
)
```

### 5. Frontend Deployment

```bash
git add .
git commit -m "Migrate to Cloudflare Pages"
git push origin main
```

GitHub Actions will automatically deploy to Cloudflare Pages.

### 6. Backend Deployment

```bash
git add .
git commit -m "Deploy backend to container platform"
git push origin main
```

GitHub Actions will build Docker image and deploy to your chosen platform.

## Verification Checklist

### Pre-Deployment

- [ ] Cloudflare account created and logged in
- [ ] R2 bucket `gems-luxury-storage` created
- [ ] wrangler installed and authenticated locally
- [ ] GitHub repository connected to Cloudflare Pages
- [ ] Container platform account created (Railway/Render/Cloudflare Run)
- [ ] All GitHub secrets configured
- [ ] Backend environment variables set in container platform
- [ ] MongoDB Atlas IP whitelist includes container platform IPs

### Post-Deployment

#### Frontend (Cloudflare Pages)
- [ ] Frontend builds successfully in GitHub Actions
- [ ] Frontend deploys to Cloudflare Pages
- [ ] Frontend loads at Pages URL
- [ ] `REACT_APP_BACKEND_URL` is set correctly in Pages settings
- [ ] Static assets (CSS, JS) load correctly
- [ ] Routing works (React Router)

#### Backend (Container Platform)
- [ ] Docker image builds successfully in GitHub Actions
- [ ] Docker image pushes to GHCR
- [ ] Backend deploys to container platform
- [ ] Backend health check passes
- [ ] Backend API responds at root URL
- [ ] MongoDB connection successful
- [ ] R2 bucket binding works (if using Workers) or R2 API access works

#### Storage (Cloudflare R2)
- [ ] Image upload works via `/api/admin/images/upload`
- [ ] Image download works via `/api/images/{id}/download`
- [ ] Image variations work (enhance, alternates)
- [ ] R2 bucket contains uploaded files
- [ ] Storage paths are correct

#### Functionality
- [ ] User authentication works (login, logout, token refresh)
- [ ] Attendance tracking works (punch in/out, break start/end)
- [ ] Auto punch-out sweep runs (check logs)
- [ ] Product generation works with AI
- [ ] PDF generation works client-side (jspdf)
- [ ] Admin dashboard loads correctly
- [ ] Activity logs are recorded

#### Performance
- [ ] Frontend loads quickly (< 2s)
- [ ] API responses are fast (< 500ms typical)
- [ ] Image uploads complete successfully
- [ ] No CORS errors in browser console

#### Monitoring
- [ ] Cloudflare Pages analytics show traffic
- [ ] Container platform logs show no errors
- [ ] MongoDB Atlas shows connection activity
- [ ] R2 bucket shows storage usage

## Rollback Plan

If issues arise:

### Frontend Rollback
1. Revert `frontend/` changes
2. Redeploy to previous hosting
3. Update DNS if needed

### Backend Rollback
1. Revert `backend/` changes
2. Redeploy to previous hosting
3. Restore previous Docker image

### Storage Rollback
1. Keep Emergent storage active during migration
2. Revert `storage.py` to Emergent API version
3. Update MongoDB paths back to Emergent

### Database Rollback
- No changes to MongoDB, always safe

## Known Limitations

1. **Scheduled Tasks**: APScheduler runs in container, not Cron Triggers
   - Impact: Container must stay running for scheduled tasks
   - Mitigation: Use platform with always-on containers

2. **PDF Generation**: Client-side only
   - Impact: Requires JavaScript, may not work in very old browsers
   - Mitigation: Modern browsers have excellent PDF support

3. **Workers Migration**: Partially prepared but not implemented
   - Impact: Full Workers migration requires additional work
   - Mitigation: Hybrid approach is production-ready

## Future Enhancements

1. **Full Workers Migration**: When Workers Python runtime is stable
   - Migrate backend to Workers
   - Use Cron Triggers for scheduled tasks
   - Use Durable Objects for state if needed

2. **Edge Functions**: Consider Cloudflare Edge Functions for specific endpoints
   - Image optimization
   - API caching
   - Edge authentication

3. **Monitoring**: Add observability
   - Cloudflare Analytics
   - Container platform monitoring
   - Error tracking (Sentry)

## Support

For issues:
1. Check README.md troubleshooting section
2. Review GitHub Actions logs
3. Check Cloudflare dashboard
4. Check container platform logs
5. Review this changelog for migration-specific issues

## Completion Date

Migration completed: April 29, 2026
