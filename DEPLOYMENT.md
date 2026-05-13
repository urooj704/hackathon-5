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

## Netlify (frontend)

This project has been optimized for a seamless deployment on Netlify using the included `netlify.toml` file.

### Deployment Steps (Premium Setup)

1. **Connect your repository**: Link your GitHub repository to Netlify.
2. **Auto-Configuration**: Netlify will automatically detect the root `netlify.toml` file. This configures Netlify to use `frontend/web-form` as the Base directory and run the correct Next.js build command.
3. **Set Environment Variables**: In the Netlify deployment settings (or later under Site configuration > Environment variables), add the following:

| Name | Value |
|------|--------|
| `NEXT_PUBLIC_API_URL` | `https://ujjee-hackathon-5.hf.space` |
| `BACKEND_URL` | `https://ujjee-hackathon-5.hf.space` |

4. **Deploy**: Click **Deploy Site**. Netlify will build your application and deploy it across its Edge network.
5. **CORS (Full Backend Only)**: If you use the full backend with strict CORS, update `CORS_ORIGINS_EXTRA` on the Hugging Face Space secrets to include your new Netlify URL (e.g. `https://your-project.netlify.app`). The default mock backend allows all origins.

### Frontend ↔ Backend Communication

Next.js API routes securely proxy requests to your Hugging Face URL via `BACKEND_URL` or `NEXT_PUBLIC_API_URL`. This prevents CORS errors on the frontend since the browser only communicates with your Netlify domain.

## Git remotes

- `origin` → GitHub
- `hf` → Hugging Face Space (for `git push hf main`)
