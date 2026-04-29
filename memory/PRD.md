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
- Attendance flow: punch in/out, break start/end, heartbeat, auto punch-out sweep logic, idle warning in worker UI
- AI product generation (Claude Sonnet 4.5) — returns name / short title / short+full description / tags / sizes / final_price (clamped to admin-configured band) + pricing_meta (admin-only)
- Pricing engine: silent background analysis, pricing_meta stripped from all worker responses
- Image library: upload to Emergent object storage, tagging, status lifecycle (available/assigned/skipped/needs_review/archived), query-param-auth download for `<img src>`
- Gemini Nano Banana: enhance image + generate 2 alternate-view variations
- Admin dashboard: KPIs (punched in / on break / idle / products today / products 7d / images / total), live worker list, recent products, activity feed
- Naming families CRUD (enable/disable, edit words), Pricing rules, Categories, Settings (idle timeout, warning seconds, break policy, feature toggles), Attendance admin (force punch-out), Activity logs
- Seed: admin + worker accounts, 9 naming families, 6 categories, default pricing rule ($40–$150), default settings
- Tests: 34/34 backend pytest cases passed; frontend end-to-end validated via testing agent

## Seed credentials
- Admin: `admin@gemsandluxury.com` / `Admin@123`
- Worker: `worker@gemsandluxury.com` / `Worker@123`

## Backlog
### P1
- Background scheduler to periodically run `auto_punch_out_sweep()` (currently logic only)
- CMS export payload endpoint (JSON blob ready for headless CMS / Shopify)
- Admin override UI for generated product pricing_meta
- Image variation browser UI (admin can view enhanced + alternates side-by-side with source)

### P2
- Prompt template editor UI (AI prompts as configurable records)
- Duplicate name detection with fuzzy search before finalizing generation
- Weekly timesheet PDF export
- Manager read-only permission fine-tuning
- Structured error alerts / email digests for admins

## Risks / assumptions
- AI calls are real (~10–15s Claude, ~15–30s Nano Banana) — add UI loading skeletons for long generations.
- Emergent object storage has no delete/rename API — soft-delete only.
- Frontend dashboard auto-refresh every 30s; for many concurrent admins, add websocket in future.
