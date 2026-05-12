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

### Option C — Root Directory = `frontend` (your current error)

If Vercel shows **`.next` not found at `.../frontend/.next`**, the project root is **`frontend`** while Next still builds in **`frontend/web-form`**.

This repo now includes **`frontend/package.json`**, **`frontend/vercel.json`**, and **`frontend/sync-next-output.js`**: install + build run inside **`web-form`**, then **`.next` is copied to `frontend/.next`** so Vercel’s Next builder finds it.

You can keep Root Directory as **`frontend`**, or switch to **A** or **B** if you prefer.

### Option A — Root Directory (recommended)

Set **Root Directory** to **`frontend/web-form`**. No extra root `package.json` is required for that layout.

### Option B — Deploy from repository root (NOT_FOUND fix)

If the project is connected with **Root Directory = `.`** (whole repo), this repo now includes a **root `package.json`** that runs `scripts/sync-frontend-to-root.js` before `next build`, copying `frontend/web-form` into the root so Vercel’s Next.js builder finds `pages/`, `next.config.js`, etc.

Either **A** or **B** works. If you use **A**, Vercel only builds the subfolder and ignores the root `package.json` for that deployment.

### Steps (Root Directory = `frontend/web-form`)

1. Import the GitHub repo and set **Root Directory** to `frontend/web-form`.
2. Framework: **Next.js** (auto-detected; `frontend/web-form/vercel.json` sets `"framework": "nextjs"`).
3. **Environment variables** (Production):

| Name | Value |
|------|--------|
| `NEXT_PUBLIC_API_URL` | Your Hugging Face Space URL, e.g. `https://ujjee-hackathon-5.hf.space` |
| `BACKEND_URL` | Same as above (used by API routes server-side) |

4. Deploy. Update `CORS_ORIGINS_EXTRA` on the backend (Hugging Face secrets) to include your Vercel URL, e.g. `https://your-project.vercel.app`, if you use the **full** backend with strict CORS. The mock backend allows all origins.

### Steps (Root Directory = repository root — `.` or empty)

1. Leave **Root Directory** blank or set to `.` (entire repository).
2. Framework: **Next.js** (detected via root `package.json` + root `vercel.json`).
3. **Build** runs `prebuild` → `scripts/sync-frontend-to-root.js` → `next build` at the repo root.
4. Set the same **environment variables** as in the table above (root `vercel.json` also sets a default `BACKEND_URL` for the HF mock API).

### Steps (Root Directory = `frontend`)

1. Leave **Root Directory** as **`frontend`** (or set it to that if you want this layout).
2. **Do not** set a custom **Output Directory** in Vercel (leave empty for Next.js).
3. Deploy: `frontend/vercel.json` runs `npm ci` in `web-form`, builds there, then copies **`web-form/.next` → `frontend/.next`**.
4. Use the same **environment variables** as in the table above (`frontend/vercel.json` includes a default `BACKEND_URL`).

## Git remotes

- `origin` → GitHub
- `hf` → Hugging Face Space (for `git push hf main`)
