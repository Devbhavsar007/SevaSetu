# SevaSetu — Deployment Guide

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                     Render.com                      │
│                                                     │
│  ┌───────────────┐  ┌──────────────────────────┐   │
│  │ sevasetu-db   │  │ sevasetu-backend          │   │
│  │ (PostgreSQL)  │←─│ (FastAPI + Uvicorn)       │   │
│  │ Free Plan     │  │ Python 3.10               │   │
│  └───────────────┘  └──────────────────────────┘   │
│                                                     │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────┐  │
│  │ sevasetu-    │ │ sevasetu-    │ │ sevasetu-  │  │
│  │ admin        │ │ volunteer    │ │ landing    │  │
│  │ (Static)     │ │ (Static)     │ │ (Static)   │  │
│  └──────────────┘ └──────────────┘ └────────────┘  │
└─────────────────────────────────────────────────────┘
```

## Prerequisites

- A [Render.com](https://render.com) account
- The GitHub repository linked to Render

## Database Setup

### 1. Create PostgreSQL Database on Render

1. Go to **Dashboard → New → PostgreSQL**
2. **Name**: `sevasetu-db`
3. **Database Name**: `sevasetu`
4. **User**: `sevasetu_user`
5. **Plan**: Free (or Starter for production)
6. **Region**: Same region as your web services
7. Click **Create Database**

### 2. Copy Connection String

After creation, go to the database dashboard and copy the **Internal Connection String**.
It will look like:
```
postgresql://sevasetu_user:PASSWORD@dpg-XXXXX-a.oregon-postgres.render.com/sevasetu
```

### 3. Configure Backend Environment

In the `sevasetu-backend` service settings → **Environment**:

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | The Internal Connection String from step 2 |
| `SECRET_KEY` | A strong random string (use `openssl rand -hex 32`) |
| `GEMINI_API_KEY` | Your Google Gemini API key |
| `GOOGLE_CLIENT_ID` | Your Google OAuth Client ID |
| `GOOGLE_CLIENT_SECRET` | Your Google OAuth Client Secret |
| `APP_ENV` | `production` |
| `DEBUG` | `false` |

> **Note**: When using `render.yaml`, the `DATABASE_URL` is auto-injected from the managed database. No manual setup needed for this variable.

## Local Development

### SQLite (Default — No Setup Required)

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The app will automatically use SQLite (`smartalloc.db`) when `DATABASE_URL` is not set.

### PostgreSQL (Optional Local)

```bash
# Set DATABASE_URL to your local PostgreSQL
export DATABASE_URL=postgresql://user:pass@localhost:5432/sevasetu

cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Verifying the Deployment

### Health Check

```bash
curl https://sevasetu-bnup.onrender.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "healthy",
  "database_engine": "postgresql",
  "environment": "production",
  "gemini_configured": true,
  "firebase_configured": false
}
```

### Key Indicators
- `database_engine` should be `postgresql` on Render
- `database_engine` should be `sqlite` in local dev
- `database` should be `healthy`

## Frontend Deployments

All three frontends (admin, volunteer, landing) are deployed as **static sites** on Render:

- **Build Command**: `npm install && npm run build`
- **Publish Directory**: `dist`

The API URL is configured in each app's `services/api.js` file.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `database: unhealthy` | Check DATABASE_URL is correct. Check DB is running. |
| `database_engine: sqlite` on Render | DATABASE_URL not set. Check environment variables. |
| CORS errors | Ensure frontend URLs are in `config.py` → `cors_origins` |
| `401 Unauthorized` | Token expired. Re-login. Check SECRET_KEY hasn't changed. |
