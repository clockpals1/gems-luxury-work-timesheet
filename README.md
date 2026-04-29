# Gems & Luxury - Internal Staff Platform

An internal staff platform for a luxury fashion brand featuring attendance tracking, AI-powered product generation, image management, and reporting.

## Architecture

This application uses a hybrid Cloudflare deployment architecture:

- **Frontend**: React SPA deployed on Cloudflare Pages
- **Backend**: Python FastAPI deployed on container-based platform (Railway/Render/Cloudflare Run)
- **Storage**: Cloudflare R2 for object storage (images, variations)
- **Database**: MongoDB Atlas
- **CI/CD**: GitHub Actions for automated deployments

### Why This Architecture?

The original architecture audit identified critical incompatibilities with running the full FastAPI application on Cloudflare Workers Python runtime (still in beta):
- APScheduler background tasks require persistent processes
- MongoDB connection pooling patterns need refactoring
- reportlab PDF generation has filesystem dependencies
- Some dependencies may not be compatible with Workers V8 isolate

The hybrid approach achieves Cloudflare benefits (Pages for frontend, R2 for storage) while maintaining backend stability on container infrastructure.

## Local Development

### Prerequisites

- Node.js 18+
- Python 3.11+
- MongoDB Atlas account (or local MongoDB)
- Cloudflare account (for R2 bucket)

### Frontend Setup

```bash
cd frontend
npm install
cp .env.example .env.local
# Edit .env.local with your backend URL
npm start
```

Frontend runs on http://localhost:3000

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your configuration
uvicorn server:app --reload
```

Backend runs on http://localhost:8000

### Environment Variables

#### Frontend (.env.local)
```
REACT_APP_BACKEND_URL=http://localhost:8000
```

#### Backend (.env)
```
MONGO_URL=mongodb+srv://username:password@cluster.mongodb.net
DB_NAME=gemsluxury
JWT_SECRET=your-secret-key-here
JWT_EXPIRES_MINUTES=720
EMERGENT_LLM_KEY=your-emergent-api-key-here
APP_NAME=gemsluxury
PUBLIC_BACKEND_URL=http://localhost:8000
CORS_ORIGINS=*
```

## Cloudflare Setup

### 1. Create R2 Bucket

1. Go to Cloudflare Dashboard → R2 → Create Bucket
2. Name it: `gems-luxury-storage`
3. Note the bucket name for wrangler.toml configuration

### 2. Configure Wrangler (for local development with R2)

```bash
npm install -g wrangler
wrangler login
```

Update `backend/wrangler.toml` with your bucket name if different.

### 3. Set GitHub Secrets

For CI/CD, configure these secrets in your GitHub repository:

**Cloudflare:**
- `CLOUDFLARE_ACCOUNT_ID` - Your Cloudflare account ID
- `CLOUDFLARE_API_TOKEN` - API token with Pages and R2 permissions

**Backend:**
- `MONGO_URL` - MongoDB connection string
- `DB_NAME` - Database name
- `JWT_SECRET` - JWT signing key
- `EMERGENT_LLM_KEY` - Emergent API key

**Frontend:**
- `REACT_APP_BACKEND_URL` - Backend API URL (set in Cloudflare Pages settings)

## Deployment

### Frontend to Cloudflare Pages

Frontend deploys automatically via GitHub Actions when pushing to `main`:

```bash
git add .
git commit -m "Update frontend"
git push origin main
```

Or deploy manually:
```bash
cd frontend
npm run build
wrangler pages deploy build --project-name=gems-luxury-frontend
```

### Backend to Container Platform

The backend is deployed via Docker. Choose your platform:

**Railway:**
1. Create new project on Railway
2. Connect GitHub repository
2. Set environment variables
3. Deploy

**Render:**
1. Create new Web Service on Render
2. Connect GitHub repository
3. Set environment variables
4. Deploy

**Cloudflare Run:**
1. Configure deployment in `.github/workflows/deploy-backend.yml`
2. Uncomment Cloudflare Run section
3. Add `CLOUDFLARE_RUN_SERVICE_ID` secret

Backend also deploys automatically via GitHub Actions when pushing to `main`.

## Storage Migration from Emergent to R2

The storage layer has been migrated from Emergent's HTTP API to Cloudflare R2. Existing images need to be migrated:

1. Export images from Emergent storage
2. Upload to R2 bucket using the new storage.py implementation
3. Update MongoDB `image_assets` collection with new storage paths

## PDF Generation

PDF generation has been moved from server-side (reportlab) to client-side (jspdf):

- Backend endpoint `/admin/reports/timesheet` now returns JSON data
- Frontend uses jspdf to generate PDFs client-side
- This removes filesystem dependencies and improves UX

## Scheduled Tasks

The auto punch-out sweep is handled by APScheduler in the backend container. For Cloudflare Workers deployment, this would use Cron Triggers, but the hybrid approach keeps it in the container for stability.

## Troubleshooting

### Frontend Build Fails
- Ensure all dependencies are installed: `npm install`
- Check environment variables in .env.local
- Verify REACT_APP_BACKEND_URL is set correctly

### Backend Storage Errors
- Ensure R2 bucket is created and accessible
- Check wrangler.toml bucket binding configuration
- Verify storage.init_storage() is called with R2 bucket

### Database Connection Issues
- Verify MONGO_URL is correct and accessible
- Check MongoDB Atlas IP whitelist includes your deployment IP
- Ensure DB_NAME matches your database name

### PDF Generation Issues
- Ensure jspdf is installed: `npm install jspdf`
- Check browser console for client-side errors
- Verify backend timesheet data endpoint returns valid JSON

## Project Structure

```
.
├── frontend/                 # React SPA
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── craco.config.js
├── backend/                  # FastAPI backend
│   ├── server.py            # Main API
│   ├── storage.py           # R2 storage wrapper
│   ├── ai_service.py        # AI integration
│   ├── requirements.txt
│   ├── Dockerfile
│   └── wrangler.toml
├── .github/
│   └── workflows/
│       ├── deploy-frontend.yml
│       └── deploy-backend.yml
└── README.md
```

## Support

For issues or questions:
1. Check this README's troubleshooting section
2. Review GitHub Actions logs for deployment failures
3. Check Cloudflare dashboard for Pages/R2 issues
4. Review container platform logs for backend issues
