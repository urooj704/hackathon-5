---
title: FlowForge AI Support
emoji: "🚀"
colorFrom: blue
colorTo: green
sdk: python
sdk_version: "0.0.0"
python_version: "3.11"
app_file: mock_backend.py
pinned: false
---

# FlowForge AI Support

**A polished AI-powered support system with a Next.js frontend and FastAPI backend, designed for multi-channel customer support and rapid local deployment.**

---

## Highlights

- Mock backend ready for instant local testing
- Full backend support with PostgreSQL + Redis
- Frontend available at `http://localhost:3001`
- Vercel deployment-ready with `NEXT_PUBLIC_API_URL`
- Connected web form and backend routing out of the box

## Quick Start

### Option 1: Fast Local Start (Mock Backend)

```bash
cd C:\Users\king\Desktop\hackaton-5
python mock_backend.py
```

### Option 2: Full Backend + Frontend

```bash
cd C:\Users\king\Desktop\hackaton-5\backend
pip install -r requirements.txt
copy .env.example .env
# Update .env with your API keys and database credentials
uvicorn src.app:app --reload --port 8000
```

```bash
cd C:\Users\king\Desktop\hackaton-5\frontend\web-form
npm install
npm run dev
```

Open the services in your browser:

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3001`

## Local Connection

The frontend is configured to use `NEXT_PUBLIC_API_URL` if set, otherwise it falls back to `http://localhost:8000`.

## Deployment Guide

### Backend

- Local mock server: `python mock_backend.py`
- Full backend:

```bash
cd backend
pip install -r requirements.txt
uvicorn src.app:app --reload --port 8000
```

### Docker

```bash
docker build -t flowforge-backend .
docker run -p 8000:8000 flowforge-backend
```

### Frontend on Vercel

Deploy from `frontend/web-form` and set:

- `NEXT_PUBLIC_API_URL=https://your-backend-url`

## API Endpoints

### Health

```http
GET /health
```

### Submit Support Request

```http
POST /channels/web-form/submit
Content-Type: application/json

{
  "name": "John Doe",
  "email": "john@example.com",
  "subject": "Technical Issue",
  "category": "technical",
  "priority": "high",
  "message": "I need help with..."
}
```

### Ticket Status

```http
GET /channels/web-form/ticket/{ticket_id}
```

## Environment Variables

```bash
ANTHROPIC_API_KEY=your_anthropic_key
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_api_key
OPENAI_API_KEY=your_openai_api_key
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/db
REDIS_URL=redis://localhost:6379/0
GMAIL_CLIENT_ID=your_client_id
GMAIL_CLIENT_SECRET=your_client_secret
GMAIL_REDIRECT_URI=http://localhost:8000/channels/gmail/oauth/callback
WHATSAPP_PHONE_NUMBER_ID=your_phone_id
WHATSAPP_ACCESS_TOKEN=your_access_token
```

## Git Remote

Your GitHub remote is configured as:

```bash
git remote -v
author origin https://github.com/urooj704/hackathon-5.git (fetch)
origin  https://github.com/urooj704/hackathon-5.git (push)
```

## Notes

- The frontend is already wired to connect to the backend.
- For local testing, use `mock_backend.py` first.
- For Vercel deployment, set `NEXT_PUBLIC_API_URL` to your backend URL.
