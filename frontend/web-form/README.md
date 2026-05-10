# FlowForge Support Form

A modern, embeddable customer support form powered by Next.js and React, with a Hugging Face backend for AI ticket processing.

## Features
- Instant AI-powered support
- Ticket tracking and status updates
- Accessible, responsive UI
- 3D visual effects (Three.js)
- Easy Vercel deployment

## Project Structure
- `pages/` — Next.js routes (API and UI)
- `components/` — React components
- `styles/` — Tailwind CSS and global styles

## Environment Variables
Copy `.env.example` to `.env.local` and fill in as needed:

```
NEXT_PUBLIC_API_URL=https://ujjee-hackathon-5.hf.space
BACKEND_URL=
```

- `NEXT_PUBLIC_API_URL`: (Required) Hugging Face backend URL for API calls
- `BACKEND_URL`: (Optional) Custom backend override

## Local Setup
1. Install dependencies:
   ```bash
   npm install
   ```
2. Create `.env.local` from `.env.example` and set variables if needed.
3. Run the development server:
   ```bash
   npm run dev
   ```
4. Visit [http://localhost:3001](http://localhost:3001)

## Production Build
To verify production build:
```bash
npm run build
npm start
```

## Vercel Deployment
1. Push this repo to GitHub.
2. Import the repo in Vercel.
3. Set environment variable `NEXT_PUBLIC_API_URL` to your Hugging Face backend URL (default: `https://ujjee-hackathon-5.hf.space`).
4. Deploy!

## Hugging Face Backend
- The backend is already deployed and live at: `https://ujjee-hackathon-5.hf.space`
- No authentication required for API endpoints.
- Endpoints used:
  - `POST /channels/web-form/submit`
  - `GET /channels/web-form/ticket/[id]`

## Troubleshooting
- If you see blank screens or API errors, check your environment variables and backend availability.
- For CORS or network issues, ensure the backend allows requests from your Vercel domain.

---

© 2026 FlowForge. All rights reserved.
