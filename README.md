---
title: FlowForge AI Support
emoji: "🚀"
colorFrom: blue
colorTo: green
sdk: docker
sdk_version: "0.0.0"
app_file: Dockerfile
pinned: false
---

# FlowForge AI Support

AI-powered customer support with a **Next.js** frontend and **FastAPI** backend. The Hugging Face Space runs a Docker image that serves the API on port `7860` (see `hf_entrypoint.py`).

## Live backend (Hugging Face)

Default Space URL (after a successful build):

**https://ujjee-hackathon-5.hf.space**

- Health: `GET /health`
- OpenAPI: `GET /docs` (mock backend always exposes docs)
- Web form: `POST /channels/web-form/submit`, `GET /channels/web-form/ticket/{id}`

By default the Space runs the **in-memory mock API** (no Postgres). For the full agent + database stack, set Space secrets and `USE_FULL_BACKEND=true` plus a remote `DATABASE_URL` (see `DEPLOYMENT.md` and `backend/.env.example`).

## Repository layout

| Path | Role |
|------|------|
| `Dockerfile` | Hugging Face Docker build |
| `hf_entrypoint.py` | Chooses mock vs full FastAPI |
| `mock_backend.py` | Lightweight API for Spaces / demos |
| `backend/` | Production FastAPI app, agents, migrations |
| `frontend/web-form/` | Next.js UI for Vercel |

## Frontend (local)

```bash
cd frontend/web-form
npm install
npm run dev
```

App listens on **http://localhost:3001**. API routes proxy to `BACKEND_URL` or `NEXT_PUBLIC_API_URL`, defaulting to the Hugging Face URL in `lib/serverBackendUrl.js`.

## Full backend (local)

```bash
cd backend
pip install -r requirements.txt
copy .env.example .env
# Edit .env: DATABASE_URL, API keys, etc.
uvicorn src.app:app --reload --port 8000
```

## Deploy

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for Hugging Face secrets and Vercel.

**Vercel:** Either set **Root Directory** to `frontend/web-form`, **or** leave Root Directory as the repo root — a root `package.json` now mirrors `frontend/web-form` before `next build`, which fixes **404 NOT_FOUND** when the whole repo is connected without a subdirectory root.

**Frontend ↔ backend:** Next.js API routes call your Hugging Face URL via `BACKEND_URL` / `NEXT_PUBLIC_API_URL` (see `frontend/web-form/lib/serverBackendUrl.js` and `vercel.json`).

## Git remotes

```text
origin → https://github.com/urooj704/hackathon-5.git
hf     → https://huggingface.co/spaces/Ujjee/hackathon-5
```

Push Space updates: `git push hf main`. Push GitHub: `git push origin main`.

## Environment templates

- Root: [.env.example](.env.example)
- Backend: [backend/.env.example](backend/.env.example)
- Frontend: [frontend/web-form/.env.example](frontend/web-form/.env.example)

Do not commit real `.env` files or API keys.
