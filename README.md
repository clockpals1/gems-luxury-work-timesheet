# Gems & Luxury — Internal Staff Platform

Internal staff platform for an African luxury fashion brand: attendance
tracking, AI-powered product generation, image management, and reporting.

## Architecture

| Layer        | Technology                                    |
| ------------ | --------------------------------------------- |
| Frontend     | React (CRA + craco) on **Cloudflare Pages**   |
| Backend      | FastAPI (Python 3.11) on **Render** (Docker)  |
| Database     | **Supabase Postgres** (JSONB)                 |
| Storage      | **Supabase Storage** (object bucket)          |
| AI — text    | **Anthropic Claude** (`anthropic` SDK)        |
| AI — images  | **Google Gemini** (`google-genai` SDK)        |
| CI / CD      | GitHub Actions                                |

Persistent collections are stored as `gl_<collection>` JSONB tables. A thin
async adapter (`backend/db.py`) exposes the small subset of MongoDB query /
update operators used by the application (`$ne`, `$gte`, `$gt`, `$lt`, `$in`,
`$exists`, `$set`, `$inc`, plus `upsert=True`) so the original handler code
runs unchanged on Postgres.

The Emergent / Cloudflare R2 / MongoDB layers from the previous iteration
have been fully removed.

## Local development

### Prerequisites

- Node.js 20+
- Python 3.11+
- A free [Supabase](https://supabase.com) project (provides Postgres + Storage)
- (Optional) Anthropic + Google AI Studio API keys for AI features

### Backend

```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate          # Windows PowerShell
# source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
cp .env.example .env              # then fill in the values
uvicorn server:app --reload --port 8000
```

Required env vars (see `backend/.env.example`):

```
DATABASE_URL=postgresql://...supabase.co:5432/postgres
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_STORAGE_BUCKET=gems-luxury
JWT_SECRET=<long random string>
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...
CORS_ORIGINS=http://localhost:3000
```

On startup the backend will:

1. Open an `asyncpg` pool to Supabase Postgres.
2. Create the `gl_*` tables and indexes if they don't yet exist.
3. Seed default admin/worker users, settings, categories, naming families,
   and prompt templates.

Default seeded credentials (change them immediately):

| Role   | Email                          | Password    |
| ------ | ------------------------------ | ----------- |
| admin  | `admin@gemsandluxury.com`      | `Admin@123` |
| worker | `worker@gemsandluxury.com`     | `Worker@123`|

### Frontend

```bash
cd frontend
yarn install
cp .env.example .env.local
# set REACT_APP_BACKEND_URL=http://localhost:8000
yarn start
```

Open <http://localhost:3000>.

## Supabase setup

1. Create a Supabase project.
2. **Database** — Project Settings → Database → Connection string. Copy
   the **Connection Pooling** URI (`*.pooler.supabase.com:6543`) and use it
   as `DATABASE_URL`.
3. **Storage** — Storage → New bucket → name it `gems-luxury` and mark it
   *private* (the backend uses the service role key to read/write).
4. **API keys** — Project Settings → API → copy the *service role* key into
   `SUPABASE_SERVICE_ROLE_KEY`.
5. (Optional) Run `backend/sql/schema.sql` from the SQL editor — the backend
   does this automatically at startup, but the file is the canonical
   reference.

## Deployment

### Backend → Render

The repo ships a Render Blueprint at the project root.

1. Push this repo to GitHub.
2. Render Dashboard → **New → Blueprint** → select the repo.
3. Render reads `render.yaml`, builds `backend/Dockerfile` and creates
   `gems-luxury-backend`. Fill in the secrets it asks for:
   `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
   `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `PUBLIC_BACKEND_URL`,
   `CORS_ORIGINS`.
4. (Optional) Service Settings → **Deploy Hook** → copy the URL into the
   GitHub repo secret `RENDER_DEPLOY_HOOK_URL`. Subsequent pushes that
   touch `backend/**` will redeploy automatically via
   `.github/workflows/deploy-backend.yml`.

Health check: `GET /health` returns `{"status":"ok"}`.

### Frontend → Cloudflare Pages

`.github/workflows/deploy-frontend.yml` builds the React app and deploys it
with `wrangler pages deploy`.

GitHub repo secrets required:

- `CLOUDFLARE_API_TOKEN` — token with the **Pages : Edit** permission.
- `CLOUDFLARE_ACCOUNT_ID`
- `REACT_APP_BACKEND_URL` — public URL of the Render backend, e.g.
  `https://gems-luxury-backend.onrender.com`.

The first deploy will create a Pages project named `gems-luxury-frontend`.
SPA routing is handled by `frontend/public/_redirects`.

## Project structure

```
.
├── backend/
│   ├── server.py          FastAPI app (≈1250 lines)
│   ├── db.py              asyncpg + JSONB Mongo-compat adapter
│   ├── storage.py         Supabase Storage REST wrapper
│   ├── ai_service.py      Anthropic + Google Gemini integrations
│   ├── sql/schema.sql     Reference DB schema
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/              React SPA
├── render.yaml            Render Blueprint
└── .github/workflows/
    ├── deploy-backend.yml   Triggers Render deploy hook
    └── deploy-frontend.yml  Builds + deploys to Cloudflare Pages
```

## Troubleshooting

- **`DATABASE_URL not set`** — environment variable missing. Check Render
  service env vars.
- **`SUPABASE_URL not set` on image upload** — ensure both `SUPABASE_URL`
  and `SUPABASE_SERVICE_ROLE_KEY` are present.
- **Image upload returns 500** — the Supabase bucket name in
  `SUPABASE_STORAGE_BUCKET` must already exist; create it in the Supabase
  dashboard.
- **AI endpoints return 500** — `ANTHROPIC_API_KEY` (text generation) or
  `GEMINI_API_KEY` (image enhance / alternates) is missing.
- **CORS errors in browser** — set `CORS_ORIGINS` on the backend to a
  comma-separated list including the Pages URL.
