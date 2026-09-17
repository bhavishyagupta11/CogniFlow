# CogniFlow Deployment Guide

This guide outlines the production deployment procedure for CogniFlow across low-cost and free cloud hosting providers.

---

## 1. Prerequisites

Before beginning deployment, ensure you have accounts and access to the following services:

- **GitHub**: Repository containing the committed CogniFlow project code.
- **Google AI Studio**: An active API key for Google Gemini (`gemini-2.5-flash` or `gemini-1.5-flash`, and `gemini-embedding-001`).
- **Supabase**: A free-tier PostgreSQL project.
- **Cloudflare**: A Cloudflare account with R2 object storage enabled.
- **Render**: An account for hosting the Python FastAPI web service.
- **Vercel**: An account for hosting the static React/Vite single-page application.

---

## 2. Architecture

```mermaid
flowchart TD
    User([Client Browser])

    subgraph CDN [Edge & Static Hosting]
        Vercel[Vercel SPA]
    end

    subgraph Compute [Compute Tier]
        Render[Render Web Service<br>FastAPI + Uvicorn]
    end

    subgraph DataServices [Managed Data Services]
        Supabase[(Supabase PostgreSQL<br>Connection Pooler)]
        R2[(Cloudflare R2<br>S3 Private Bucket)]
        Gemini[Google Gemini API<br>LLM & Embeddings]
    end

    User -->|HTTPS| Vercel
    User -->|HTTPS / SSE| Render
    Render -->|SQL Queries| Supabase
    Render -->|S3 Upload / Download| R2
    Render -->|API Calls| Gemini
```

---

## 3. Supabase PostgreSQL Setup

CogniFlow uses PostgreSQL for relational data persistence (users, chats, messages, document metadata, chunks, and summaries).

### 1. Create Project
1. Log in to the [Supabase Dashboard](https://supabase.com/dashboard) and click **New Project**.
2. Select an organization, provide a project name (such as `cogniflow-db`), generate a strong database password, and choose a region close to your planned Render compute deployment.

### 2. Apply the Database Schema
1. In the Supabase Dashboard, navigate to the **SQL Editor** in the left navigation.
2. Click **New Query**.
3. Copy the entire contents of [`backend/db/schema.sql`](../backend/db/schema.sql).
4. Paste the SQL script into the query editor and click **Run**.
5. Verify that the tables (`users`, `conversations`, `messages`, `documents`, `document_chunks`, `document_embeddings`, `document_summaries`) and their respective indexes have been created.

### 3. Obtain Connection String
1. Go to **Project Settings** -> **Database**.
2. Under **Connection string**, navigate to the **Connection Pooling** tab.
3. Select the pooling mode appropriate for your environment:
   - **Session Pooler (Port 5432, Recommended for CogniFlow)**: CogniFlow manages its own client-side connection pool via `psycopg2.pool.ThreadedConnectionPool` (capped at 10 connections in `backend/services/db_service.py`). The Supabase Session Pooler on port 5432 provides full PostgreSQL session compatibility, supports prepared statements, and avoids residential ISP/firewall blocks that can affect port 6543. This is the verified configuration used for local development and single-instance Render deployments.
   - **Transaction Pooler (Port 6543)**: Intended for high-concurrency serverless deployments with many ephemeral workers. If configured on Render, ensure outbound connections on port 6543 are permitted by your hosting tier.
4. Copy the connection URI:
   - **Session Pooler URI (Port 5432)**:
     ```
     postgresql://postgres.[project-ref]:[db-password]@aws-0-[region].pooler.supabase.com:5432/postgres?sslmode=require
     ```
   - **Transaction Pooler URI (Port 6543)**:
     ```
     postgresql://postgres.[project-ref]:[db-password]@aws-0-[region].pooler.supabase.com:6543/postgres?sslmode=require
     ```
   Replace `[db-password]` with your actual database password. This URI serves as the `DATABASE_URL` environment variable.

---

## 4. Cloudflare R2 Setup

CogniFlow stores original document PDFs and extracted text artifacts in a private Cloudflare R2 bucket.

### 1. Create Private Bucket
1. Log in to the [Cloudflare Dashboard](https://dash.cloudflare.com/) and navigate to **R2**.
2. Click **Create bucket**.
3. Name the bucket (for example: `cogniflow-storage`).
4. Keep the default visibility settings (**Private**). Do not enable public access.

### 2. Object Layout
CogniFlow arranges uploaded files according to the following key structure:
- `uploads/{document_id}/original`: The uploaded binary PDF file.
- `extracted/{document_id}/pages.json`: Extracted text content structured by page number.

### 3. Generate API Credentials
1. On the R2 overview page, click **Manage R2 API Tokens** under **Account details** on the right side.
2. Click **Create API token**.
3. Select **Object Read & Write** permissions.
4. Set bucket scoping to **Specific bucket only** and select your created bucket.
5. Click **Create API Token**.
6. Record the displayed credentials:
   - **Access Key ID**: Corresponds to `R2_ACCESS_KEY_ID`.
   - **Secret Access Key**: Corresponds to `R2_SECRET_ACCESS_KEY`.
   - **Endpoint URL**: Format `https://<account_id>.r2.cloudflarestorage.com`.
   - **Account ID**: Corresponds to `R2_ACCOUNT_ID`.

---

## 5. Backend Environment Configuration

The backend application reads its configuration from environment variables defined in [`backend/config.py`](../backend/config.py).

| Variable Name | Status | Description |
| :--- | :---: | :--- |
| `DATABASE_URL` | **Required** | PostgreSQL connection string (Supabase connection pooler URI). |
| `STORAGE_BACKEND` | **Required** | Must be set to `r2` for production cloud storage. |
| `R2_ACCOUNT_ID` | **Required** | Cloudflare account identifier. |
| `R2_ACCESS_KEY_ID` | **Required** | Cloudflare R2 API token access key. |
| `R2_SECRET_ACCESS_KEY` | **Required** | Cloudflare R2 API token secret key. |
| `R2_BUCKET_NAME` | **Required** | Cloudflare R2 bucket name (e.g., `cogniflow-storage`). |
| `R2_ENDPOINT` | Optional | S3 endpoint URL (`https://<account_id>.r2.cloudflarestorage.com`). If omitted, it is constructed from `R2_ACCOUNT_ID`. |
| `GEMINI_API_KEY` | **Required** | Google AI Studio Gemini API key for text generation and embeddings. |
| `OPENROUTER_API_KEY` | Optional | Fallback API key for OpenRouter models if configured. |
| `JWT_SECRET` | **Required** | Cryptographic random string used for signing and verifying user session JWTs. |
| `CORS_ORIGINS` | **Required** | Comma-separated list of allowed frontend origins (e.g., `https://cogniflow.vercel.app`). |
| `PORT` | Optional | Listening port for the application server (Render automatically sets this; default: `3001`). |
| `HOST` | Optional | Binding interface address (default: `0.0.0.0`). |

---

## 6. Local Cloud-Backed Verification

Before deploying to Render, verify that your local environment connects successfully to the cloud Supabase and Cloudflare R2 instances:

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Populate `.env` with your real cloud credentials:
   ```ini
   DATABASE_URL=postgresql://postgres.[ref]:[pwd]@aws-0-[region].pooler.supabase.com:5432/postgres?sslmode=require
   STORAGE_BACKEND=r2
   R2_ACCOUNT_ID=<your-account-id>
   R2_ACCESS_KEY_ID=<your-access-key-id>
   R2_SECRET_ACCESS_KEY=<your-secret-access-key>
   R2_BUCKET_NAME=cogniflow-storage
   GEMINI_API_KEY=<your-gemini-key>
   JWT_SECRET=<random-64-character-secret>
   CORS_ORIGINS=http://localhost:5173
   ```
3. Run the complete backend test suite:
   ```bash
   python -m pytest backend/tests/ -v
   ```
   All tests should pass, confirming connectivity and proper permissions across Supabase, Cloudflare R2, and Gemini.

---

## 7. Render Backend Deployment

CogniFlow includes a blueprint definition in [`render.yaml`](../render.yaml) for automated service deployment.

### 1. Create Web Service
1. Log in to [Render](https://dashboard.render.com/) and click **New +** -> **Blueprint**.
2. Select your GitHub repository. Render reads `render.yaml` and prepares the `cogniflow-api` web service.
3. Alternatively, click **New +** -> **Web Service** and configure:
   - **Name**: `cogniflow-api`
   - **Language**: `Python`
   - **Branch**: `main`
   - **Build Command**: `pip install -r backend/requirements.txt`
   - **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path**: `/api/health`
   - **Instance Type**: `Free`

### 2. Configure Environment Variables
In the service **Environment** tab, configure the variables documented in Section 5:
- Set `DATABASE_URL`, `STORAGE_BACKEND=r2`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, and `GEMINI_API_KEY`.
- Set `JWT_SECRET` (can be generated automatically via Render or set to a random hex string).
- Set `CORS_ORIGINS` to include your Vercel URL (e.g., `https://cogniflow.vercel.app`).
- Set `PYTHON_VERSION` to `3.12.4`.

### 3. Deploy
Trigger the initial deployment. Once the build completes, verify service readiness:
```bash
curl https://cogniflow-api.onrender.com/api/health
```
Expected response: `{"status":"ok"}`.

---

## 8. Vercel Frontend Deployment

The client application is configured for Vercel using [`vercel.json`](../vercel.json).

### 1. Import Project
1. Log in to [Vercel](https://vercel.com/) and click **Add New...** -> **Project**.
2. Select your GitHub repository.

### 2. Configure Build Settings
Verify the build configuration:
- **Framework Preset**: `Vite`
- **Root Directory**: `./` (or `client` if deploying client repository directly). When building from root using `vercel.json`:
  - **Build Command**: `npm ci --prefix client && npm run build --prefix client`
  - **Output Directory**: `client/dist`

### 3. Environment Variables
In the Vercel project settings under **Environment Variables**, add:
- `VITE_API_BASE_URL`: URL of your deployed Render backend (e.g., `https://cogniflow-api.onrender.com`).

### 4. SPA Routing
`vercel.json` contains URL rewrite rules forwarding non-static requests to `/index.html`:
```json
{
  "buildCommand": "npm ci --prefix client && npm run build --prefix client",
  "outputDirectory": "client/dist",
  "rewrites": [
    {
      "source": "/(.*)",
      "destination": "/index.html"
    }
  ]
}
```
This ensures direct navigation to `/documents`, `/evaluation`, `/architecture`, and `/auth` routes resolves correctly without HTTP 404 errors.

---

## 9. CORS Configuration

To allow frontend requests from Vercel to reach the Render backend, Cross-Origin Resource Sharing (CORS) must be configured in Render:

1. Copy your public Vercel production domain (e.g., `https://cogniflow.vercel.app`).
2. In Render, navigate to `cogniflow-api` -> **Environment**.
3. Update `CORS_ORIGINS`:
   ```
   https://cogniflow.vercel.app,http://localhost:5173
   ```
4. Save changes. Render automatically redeploys with the updated origins.

---

## 10. Production Smoke Test

Verify the live deployment through this verification sequence:

1. **User Registration**: Open the Vercel app URL, navigate to `/auth`, and create a new user account. Verify that you are automatically logged in.
2. **Conversation Creation**: Navigate to the chat view and verify that a default conversation is created.
3. **Document Ingestion**: Navigate to `/documents` and upload a small reference PDF. Monitor the progress indicators until the status transitions to `indexed`.
4. **Data Verification**:
   - Check the Supabase table editor to confirm new rows in `documents` and `document_chunks`.
   - Check the Cloudflare R2 bucket to confirm stored files under `uploads/` and `extracted/`.
5. **RAG Query Execution**: Submit a prompt grounded in the uploaded document. Confirm that:
   - Responses stream progressively via SSE.
   - Grounded answers contain discrete evidence tags (e.g., `[E1]`).
   - The citation panel populates with document titles and page ranges.
6. **PDF Viewer Validation**: Click **Open PDF** on a citation card. Confirm that the embedded PDF.js viewer opens and navigates directly to the cited page.
7. **Document Deletion**: Navigate to `/documents` and delete the document. Confirm that:
   - The document is removed from the catalog.
   - The document row and chunks are deleted from Supabase.
   - The original file and extracted JSON are deleted from R2.
8. **Restart Recovery**: In Render, click **Manual Deploy** -> **Restart Service**. Wait for the service to restart, then reload the client app. Verify that user accounts, chat threads, and remaining documents persist across restarts.

---

## 11. Troubleshooting

### Database Connection Failures
- **Symptom**: Backend startup logs report connection timeouts, hangs, or SSL connection errors.
- **Remedy**:
  - Ensure the connection string includes `?sslmode=require`.
  - If using port `6543` and connections hang or time out, switch to the Supabase Session Pooler on port `5432` (`aws-0-[region].pooler.supabase.com:5432`), which aligns directly with `psycopg2.pool.ThreadedConnectionPool` and avoids port 6543 network restrictions.
  - Check whether the database password contains special characters that require URL-encoding.

### Cloudflare R2 Access Denied (HTTP 403)
- **Symptom**: File uploads fail with `ClientError: An error occurred (403) when calling the PutObject operation`.
- **Remedy**:
  - Verify that the R2 API token has **Object Read & Write** permissions.
  - Ensure `R2_BUCKET_NAME` matches the bucket name in Cloudflare exactly.
  - Verify that `R2_ACCOUNT_ID` matches your Cloudflare account ID.

### CORS Origin Errors
- **Symptom**: Browser console displays `Access to fetch at ... from origin ... has been blocked by CORS policy`.
- **Remedy**:
  - Check the exact origin reported in the browser console.
  - Ensure the protocol (`https://`), domain, and port match what is listed in `CORS_ORIGINS`.
  - Do not include trailing slashes in `CORS_ORIGINS`.

### Blank Client Screen or 404 on Refresh
- **Symptom**: Direct navigation to `/chat` or `/documents` returns a 404 from Vercel.
- **Remedy**: Ensure `vercel.json` is committed in the repository root and contains the SPA rewrite block mapping `/(.*)` to `/index.html`.

### Slow Initial Request (Cold Start)
- **Symptom**: First request after an idle period takes 30–60 seconds.
- **Remedy**: Render free-tier web services spin down after 15 minutes of inactivity. Subsequent requests execute at standard speed. Use an external uptime monitor (such as UptimeRobot) targeting `/api/health` if continuous availability is needed.

---

## 12. Security Guidelines

- **Environment Isolation**: Never commit `.env` or local secret files to version control. The repository `.gitignore` is configured to prevent tracking of `.env` and `.env.*`.
- **Credential Segregation**: All storage keys, database credentials, and AI API keys must be configured exclusively in the Render backend environment.
- **Private Storage**: Cloudflare R2 bucket permissions must remain strictly private. Document streaming is authorized and proxied exclusively through backend routes (`/api/documents/{id}/pdf`).
- **Session Tokens**: Set a cryptographically secure `JWT_SECRET` in production. Tokens expire automatically and are signed using HMAC-SHA256.

---

## 13. Current Deployment Constraints

- **In-Memory Rebuild on Boot**: The vector store rebuilds its sparse and dense indices in memory upon backend startup by reading stored chunks from PostgreSQL. Startup duration scales with chunk volume.
- **Single-Process Task Execution**: Background operations (such as document summary precomputation) execute inside the application event loop. The system is designed for single-instance deployments.
- **Ephemeral Filesystem**: The local filesystem on Render free tier is ephemeral. Any temporary scratch files written outside PostgreSQL or Cloudflare R2 are wiped when the container restarts.
- **Free-Tier Limits**: Supabase free projects allow up to 500 MB of database storage. Cloudflare R2 provides 10 GB of free storage per month. Render free web services provide 512 MB RAM and spin down when idle.
