# Gems & Luxury — Internal Staff Platform

## Problem statement (verbatim)
Internal web application for Gems & Luxury (gemsandluxury.com), an African luxury clothing e-commerce brand. Staff generate AI-assisted product entries (name, descriptions, category, tags, sizes, a clean final price, and assigned image) and track work sessions (punch in/out, breaks, idle detection, auto punch-out). Admins manage users, naming families, pricing rules, image library, attendance, activity logs, and configurable settings. Workers see only a clean final selling price — never pricing research or confidence scores.

## User personas
- **Admin**: Owner/lead — manages users, business rules (pricing, naming, categories, settings), reviews everything, can force punch-out, export products. Has access to pricing_meta/reasoning.
- **Manager**: Read-only admin dashboards (users, attendance, products, activity).
- **Worker**: Punches in → generates products → punches out. Sees only final_price, never pricing reasoning.

## Architecture
- Backend: FastAPI + MongoDB (Motor), JWT auth (bcrypt), all routes `/api/*`
- AI: **Claude Sonnet 4.5** (text — product name, descriptions, silent pricing) and **Gemini Nano Banana** (image enhance + alternate views) via Emergent Universal LLM key + `emergentintegrations`
- Storage: **Emergent managed object storage** for admin-uploaded product images + AI variations
- Frontend: React 19 + Tailwind + shadcn + framer-motion, dark "Jewel & Luxury" theme (#050A07 / emerald / gold #D4AF37), Playfair Display + Manrope

## Implemented (2026-04-29)
- JWT email/password auth with bcrypt, role-based dependencies (admin / manager / worker)
- Admin user CRUD (create, list, patch)
- Attendance flow: punch in/out, break start/end, heartbeat, idle warning in worker UI
- AI product generation (Claude Sonnet 4.5) — returns name / short title / short+full description / tags / sizes / final_price (clamped to admin-configured band) + pricing_meta (admin-only)
- Pricing engine: silent background analysis, pricing_meta stripped from all worker responses
- Image library: upload to Emergent object storage, tagging, status lifecycle, query-param-auth download
- Gemini Nano Banana: enhance image + generate 2 alternate-view variations
- Admin dashboard: KPIs, live workers, recent products, activity feed
- Naming families CRUD, Pricing rules, Categories, Settings, Attendance admin (force punch-out), Activity logs
- Tests: 34/34 backend + frontend e2e

## Iteration 3 (2026-04-29) — Production hardening
- **AI prompts moved to MongoDB** (`prompt_templates` collection, seeded on startup) — no longer hardcoded in `ai_service.py`
- **Prompt template editor UI** at `/admin/prompts` — admin can edit name/description/provider/model/system_prompt/user_prompt_template/enabled with live save
- **Fuzzy duplicate-name detection** via `rapidfuzz.token_set_ratio` (threshold 85) — generation retries up to 2× with avoid-list if proposed name is too similar to recent products
- **Weekly timesheet PDF** export at `/api/admin/reports/timesheet?days=N` (reportlab) — branded summary + per-day detail; UI download button on Attendance page with 7/14/30/60/90-day selector
- **Self-service password change** (`POST /api/auth/change-password`) — sidebar/header dialog for any logged-in user
- **Admin password reset** (`POST /api/admin/users/{id}/reset-password`) — admin-only, button per user row
- **Role assignment by admin** — inline Role select per user (worker/manager/admin); admins can promote others to admin
- **Login page cleaned** — removed test credentials hint and pre-filled defaults
- **`.gitignore`** unblocked `.env` files for Emergent deploy
- Tests: 13/13 backend pass; frontend 100%; deployment_agent **PASS**

## Seed credentials
- Admin: `admin@gemsandluxury.com` / `Admin@123` (rotate via `/auth/change-password` once signed in)

## Backlog
### P1
- "Publish to Shopify" one-click direct push using `cms-payload`
- Admin-managed naming families used per-category (currently global)
- Email digest of overnight idle / auto-punch-out events

### P2
- Manager read-only permission fine-tuning per page
- Audit-trail diff view per product
- Per-prompt usage analytics (tokens, latency, success rate)

## Risks / assumptions
- AI calls are real (~10–15s Claude, ~15–30s Nano Banana) — add UI loading skeletons for long generations.
- Emergent object storage has no delete/rename API — soft-delete only.
- Frontend dashboard auto-refresh every 30s; for many concurrent admins, add websocket in future.
