# 🚀 FlowForge AI Support

> **AI-powered customer support across Gmail, WhatsApp, and Web Form.**
> One AI agent. Three channels. Tickets resolved in under 5 minutes — automatically, 24/7.

[![Live Demo](https://img.shields.io/badge/Live%20Demo-hackathon--05.netlify.app-blue?style=flat-square)](https://hackathon-05.netlify.app)
[![Backend](https://img.shields.io/badge/Backend-HuggingFace%20Space-yellow?style=flat-square)](https://ujjee-hackathon-5.hf.space)
[![Frontend](https://img.shields.io/badge/Frontend-Netlify-00C7B7?style=flat-square)](https://hackathon-05.netlify.app)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](#)

---

## 🌐 Live Links

| Service | URL |
|---|---|
| 🖥️ Frontend (Netlify) | https://hackathon-05.netlify.app |
| ⚙️ Backend (Hugging Face) | https://ujjee-hackathon-5.hf.space |
| 📖 API Docs | https://ujjee-hackathon-5.hf.space/docs |
| ❤️ Health Check | https://ujjee-hackathon-5.hf.space/health |
| 🎫 Submit Ticket | https://hackathon-05.netlify.app/support |

---

## ✨ Features

- 🧠 **Urooj Waheed AI Engine** — Context-aware, multi-turn AI responses with NLP and tool use
- 📚 **Semantic Knowledge Search** — pgvector + cosine similarity finds the right answer in milliseconds
- 🔀 **Smart Escalation Engine** — Detects frustration via sentiment analysis, auto-routes to humans
- 🎫 **Full Ticket Lifecycle** — Every message becomes a tracked ticket with cross-channel identity resolution
- ⚡ **Multi-Channel Real-time** — One AI brain across Gmail, WhatsApp, and Web Form
- 📊 **Analytics & Metrics** — Resolution rates, escalation trends, and sentiment scores by channel

---

## 📡 Channels

| Channel | Status | Details |
|---|---|---|
| 📧 Gmail | ✅ Production | OAuth2, Google Pub/Sub webhooks, thread-aware replies |
| 💬 WhatsApp | ✅ Production | Meta Cloud API, real-time messaging |
| 🌐 Web Form | ✅ Production | Instant ticket creation, AI reply in < 5 min |

---

## 🏗️ Architecture

```
┌─────────────────────┐         ┌──────────────────────────┐
│   Frontend          │         │   Backend                │
│   Next.js 14        │ ──────► │   FastAPI (Python)       │
│   Netlify CDN       │         │   Hugging Face Spaces    │
│   Port: 3001        │         │   Port: 7860             │
└─────────────────────┘         └──────────────────────────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    ▼                     ▼                     ▼
             PostgreSQL              Redis Queue           OpenAI API
             + pgvector             (Job Queue)           (Embeddings)
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 14, Tailwind CSS, Three.js (3D scene) |
| **Backend** | FastAPI (Python), Uvicorn |
| **AI Engine** | OpenAI GPT, Embeddings API |
| **Database** | PostgreSQL + pgvector (semantic search) |
| **Queue** | Redis |
| **Email** | Gmail OAuth2 + Google Pub/Sub |
| **WhatsApp** | Meta Cloud API |
| **Deployment** | Hugging Face Spaces (Docker) + Netlify |

---

## 📁 Repository Layout

```
hackathon-5/
├── Dockerfile               # Hugging Face Docker build
├── hf_entrypoint.py         # Chooses mock vs full FastAPI app
├── mock_backend.py          # Lightweight API for Spaces / demos
├── DEPLOYMENT.md            # Full deployment guide
├── .env.example             # Root env template
├── backend/
│   ├── src/
│   │   └── app.py           # Production FastAPI app
│   ├── agents/              # AI agent logic
│   ├── migrations/          # Database migrations
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    └── web-form/
        ├── app/             # Next.js app directory
        ├── lib/
        │   └── serverBackendUrl.js   # API proxy config
        ├── .env.example
        └── package.json
```

---

## 🚀 How It Works

```
 📨 Message Received        🔍 Context Built          🧠 AI Responds           ✅ Delivered
 Via Email, WhatsApp,  →   Fetches ticket history, → Generates personalized → Sent on same channel.
 or Web Form               customer profile &         reply or escalates       Ticket updated.
                           knowledge base search      with full context        Customer delighted.
```

---

## 💻 Local Development

### Frontend

```bash
cd frontend/web-form
npm install
npm run dev
# Runs on http://localhost:3001
```

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env: DATABASE_URL, OPENAI_API_KEY, etc.
uvicorn src.app:app --reload --port 8000
```

### Environment Variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `OPENAI_API_KEY` | OpenAI API key for AI + embeddings |
| `USE_FULL_BACKEND` | `true` for full stack, `false` for mock |
| `NEXT_PUBLIC_API_URL` | HuggingFace backend URL |
| `BACKEND_URL` | Server-side backend URL |

> ⚠️ Never commit real `.env` files or API keys to the repository.

---

## ☁️ Deployment

### Backend → Hugging Face Spaces

```bash
# Push to Hugging Face
git push hf main

# Push to GitHub
git push origin main
```

**Required Space Secrets:**
- `OPENAI_API_KEY`
- `DATABASE_URL` (remote PostgreSQL)
- `USE_FULL_BACKEND=true`

### Frontend → Netlify

1. Connect repository to Netlify
2. Netlify auto-detects `netlify.toml` (base dir: `frontend/web-form`)
3. Add environment variables in **Site Configuration → Environment Variables:**

```
NEXT_PUBLIC_API_URL = https://ujjee-hackathon-5.hf.space
BACKEND_URL        = https://ujjee-hackathon-5.hf.space
```

4. Click **Deploy Site** ✅

> See [DEPLOYMENT.md](./DEPLOYMENT.md) for the complete guide.

---

## 🔗 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/docs` | OpenAPI interactive docs |
| `POST` | `/channels/web-form/submit` | Submit a support ticket |
| `GET` | `/channels/web-form/ticket/{id}` | Get ticket status by ID |

---

## 👩‍💻 Built By

**Urooj** — AI-Enabled Full-Stack & Cloud-Native Developer

[![GitHub](https://img.shields.io/badge/GitHub-urooj704-black?style=flat-square&logo=github)](https://github.com/urooj704)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-urooj--anxari-blue?style=flat-square&logo=linkedin)](https://linkedin.com/in/urooj-anxari)

---

## 📄 License

MIT License — feel free to use, modify, and distribute.

---

<div align="center">
  <b>FlowForge</b> · AI-powered support across Gmail, WhatsApp & Web · Built with ❤️ by Urooj
</div>


Do not commit real `.env` files or API keys.
