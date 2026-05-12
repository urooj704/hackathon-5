# Deployment guide

## Hugging Face Space (backend)

This repository is configured as a **Docker** Space. The container runs `hf_entrypoint.py`, which starts:

- **Default:** `mock_backend` — in-memory FastAPI (no Postgres). Survives free-tier Spaces and is enough for the support form demo.
- **Full stack:** set `USE_FULL_BACKEND=true` and a remote `DATABASE_URL` (plus Redis/LLM keys as in `backend/.env.example`).

### Space secrets (full backend only)

Add variables in the Space **Settings → Variables and secrets** (same names as in `backend/.env.example`, uppercase).

### Default public API URL

After the Space builds, the API is typically:

`https://ujjee-hackathon-5.hf.space`

Verify:

- `GET /health`
- `GET /docs` (OpenAPI; enabled when `ENABLE_API_DOCS=true` on full backend; mock always has `/docs`)

### Local Docker

```bash
docker build -t flowforge-space .
docker run -p 7860:7860 -e PORT=7860 flowforge-space
```

## Vercel (frontend)

### Required: Root Directory

The Next.js app lives under **`frontend/web-form`**, not the repository root (there is no `package.json` at the repo root). In Vercel:

**Settings → General → Root Directory** → set to **`frontend/web-form`** → Save → redeploy.

If Root Directory is left as `.` (repository root), Vercel will not detect Next.js and you will see **`404: NOT_FOUND`** (or an empty deployment) when opening the site.

### Steps

1. Import the GitHub repo and set **Root Directory** to `frontend/web-form`.
2. Framework: **Next.js** (auto-detected; `vercel.json` in that folder sets `"framework": "nextjs"`).
3. **Environment variables** (Production):

| Name | Value |
|------|--------|
| `NEXT_PUBLIC_API_URL` | Your Hugging Face Space URL, e.g. `https://ujjee-hackathon-5.hf.space` |
| `BACKEND_URL` | Same as above (used by API routes server-side) |

4. Deploy. Update `CORS_ORIGINS_EXTRA` on the backend (Hugging Face secrets) to include your Vercel URL, e.g. `https://your-project.vercel.app`, if you use the **full** backend with strict CORS. The mock backend allows all origins.

## Git remotes

- `origin` → GitHub
- `hf` → Hugging Face Space (for `git push hf main`)
