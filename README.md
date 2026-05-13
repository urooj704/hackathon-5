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
| `frontend/web-form/` | Next.js UI for Netlify |

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

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for Hugging Face secrets and Netlify setup.

**Netlify Deployment (Premium Setup):**
1. Connect your repository to **Netlify**.
2. Netlify will automatically detect the `netlify.toml` configuration in the root directory.
3. The build settings will be automatically applied (`Base directory` will be `frontend/web-form`).
4. Navigate to **Site configuration > Environment variables**.
5. Add the following environment variables:
   - `NEXT_PUBLIC_API_URL` = `https://ujjee-hackathon-5.hf.space`
   - `BACKEND_URL` = `https://ujjee-hackathon-5.hf.space`
6. Click **Deploy Site**. Your Next.js app will build and deploy on Netlify's premium global edge network.

**Frontend ↔ backend:** Next.js API routes securely proxy to your Hugging Face backend via `BACKEND_URL` / `NEXT_PUBLIC_API_URL` (see `frontend/web-form/lib/serverBackendUrl.js`).

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
