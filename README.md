# FlowForge AI Support

<div align="center">

![FlowForge Logo](https://img.shields.io/badge/FlowForge-AI%20Support-blue?style=for-the-badge&logo=artificial-intelligence)
![Hackathon](https://img.shields.io/badge/Hackathon-5-success?style=for-the-badge&logo=hackathon)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**AI-Powered Multi-Channel Customer Support System**

[Live Demo](https://huggingface.co/spaces/Ujjee/hackathon-5) • [Documentation](#-documentation) • [Features](#-features)

</div>

---

## 🎯 Overview

FlowForge AI Support is an intelligent customer support system that leverages advanced AI models to provide instant, accurate responses across multiple communication channels. Built for **Hackathon 5**, this system demonstrates modern AI integration with enterprise-grade architecture.

## ✨ Features

### 🤖 AI-Powered Responses
- **Multi-Model Support**: Claude, Gemini, and Groq AI models
- **Context-Aware**: Understands conversation history and ticket context
- **Knowledge Base**: Vector-based semantic search for accurate responses
- **Auto-Escalation**: Intelligent routing to human agents for complex issues

### 📱 Multi-Channel Support
- **Web Form**: Real-time ticket submission and tracking
- **Gmail Integration**: OAuth-based email processing
- **WhatsApp**: Meta Cloud API integration
- **Unified Dashboard**: Centralized ticket management

### 🎨 Modern UI/UX
- **Responsive Design**: Works seamlessly on all devices
- **Real-time Updates**: Live ticket status polling
- **3D Visualizations**: Interactive Three.js elements
- **Accessibility**: ARIA labels and keyboard navigation

### 🔒 Enterprise Features
- **Ticket Management**: Complete lifecycle tracking
- **Priority Classification**: Automatic urgency detection
- **Category Routing**: Smart issue categorization
- **Audit Logging**: Comprehensive activity tracking

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ Web Form    │  │ Dashboard   │  │ Analytics   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  Backend (FastAPI)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ API Gateway │  │ Agent Core  │  │ Channels    │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                     Infrastructure                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ PostgreSQL  │  │    Redis    │  │   Kafka     │         │
│  │  + pgvector │  │   Cache     │  │  Messaging  │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

## 🛠️ Tech Stack

### Backend
```yaml
Framework: FastAPI 0.136+
Language: Python 3.11
AI Models:
  - Anthropic Claude (claude-sonnet-4-6)
  - Google Gemini (gemini-2.0-flash)
  - Groq (llama-3.3-70b-versatile)
Database:
  - PostgreSQL 15+ with pgvector extension
  - Redis 7+ for caching
Messaging: Kafka (aiokafka)
Email: Gmail API with OAuth
```

### Frontend
```yaml
Framework: Next.js 14.2
Language: TypeScript 5.4
Styling: Tailwind CSS 3.4
3D Graphics: Three.js 0.183
State Management: React Hooks
Build Tool: SWC (Fast Rust compiler)
```

### DevOps
```yaml
Containerization: Docker
CI/CD: GitHub Actions (planned)
Deployment:
  - Backend: Hugging Face Spaces
  - Frontend: Vercel
Monitoring: Structlog + Health Checks
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (optional for mock mode)
- Redis 7+ (optional for mock mode)

### Backend Setup

```bash
# Clone the repository
git clone https://github.com/urooj704/hackathon-5.git
cd hackathon-5

# Option 1: Quick Start (Mock Backend - No Database)
python mock_backend.py

# Option 2: Full Setup (Requires PostgreSQL + Redis)
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
uvicorn src.app:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend/web-form
npm install
npm run dev
```

Access the application at: **http://localhost:3001**

## 🌐 Deployment

### Hugging Face Spaces (Backend)
The backend is deployed using the mock backend for instant setup:
- **URL**: https://huggingface.co/spaces/Ujjee/hackathon-5
- **Status**: ✅ Live
- **Type**: Docker-based deployment

### Vercel (Frontend)
Frontend deployment configuration included:
```bash
# Deploy to Vercel
vercel deploy
```

## 📡 API Documentation

### Web Form Endpoints

#### Submit Support Request
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

#### Get Ticket Status
```http
GET /channels/web-form/ticket/{ticket_id}
```

Response:
```json
{
  "ticket_id": "TKT-ABC123",
  "status": "waiting_customer",
  "messages": [
    {
      "body": "Customer message",
      "is_from_customer": true
    },
    {
      "body": "AI response",
      "is_from_customer": false
    }
  ]
}
```

### Health Check
```http
GET /health
```

## 🔑 Environment Variables

```bash
# AI Models
ANTHROPIC_API_KEY=your_anthropic_key
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key
OPENAI_API_KEY=your_openai_key  # For embeddings

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/db
REDIS_URL=redis://localhost:6379/0

# Gmail Integration
GMAIL_CLIENT_ID=your_client_id
GMAIL_CLIENT_SECRET=your_client_secret
GMAIL_REDIRECT_URI=http://localhost:8000/channels/gmail/oauth/callback

# WhatsApp
WHATSAPP_PHONE_NUMBER_ID=your_phone_id
WHATSAPP_ACCESS_TOKEN=your_access_token
```

## 📊 Project Structure

```
hackathon-5/
├── backend/                    # FastAPI Backend
│   ├── src/
│   │   ├── app.py             # Application entry point
│   │   ├── agent/             # AI agent logic
│   │   │   ├── core.py        # Main agent pipeline
│   │   │   └── tools.py       # AI tools and functions
│   │   ├── channels/          # Channel handlers
│   │   │   ├── web_form.py    # Web form processor
│   │   │   ├── gmail.py       # Gmail integration
│   │   │   └── whatsapp.py    # WhatsApp integration
│   │   ├── db/                # Database models
│   │   ├── knowledge/         # Knowledge base
│   │   └── config.py          # Configuration
│   ├── requirements.txt       # Python dependencies
│   └── Dockerfile             # Container configuration
├── frontend/
│   └── web-form/              # Next.js Frontend
│       ├── pages/             # React pages
│       │   ├── index.jsx      # Landing page
│       │   └── support.jsx    # Support form page
│       ├── components/        # Reusable components
│       ├── SupportForm.jsx    # Main form component
│       ├── package.json       # Node dependencies
│       └── next.config.js     # Next.js configuration
├── mock_backend.py            # Simplified backend for demo
├── vercel.json                # Vercel deployment config
└── README.md                  # This file
```

## 🎨 Screenshots

### Web Form Interface
- Clean, modern design with dark theme
- Real-time validation and character count
- Ticket ID display with enhanced visibility
- Agent response polling (every 5 seconds)

### Dashboard Features
- Ticket status tracking
- Priority indicators
- Category selection
- Real-time updates

## 🔧 Development

### Running Tests
```bash
cd backend
pytest tests/
```

### Code Style
- **Python**: PEP 8 compliant
- **JavaScript**: ESLint + Prettier
- **TypeScript**: Strict mode enabled

### Database Migrations
```bash
cd backend
alembic upgrade head
```

## 🤝 Contributing

This project was developed for **Hackathon 5**. Contributions are welcome!

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 👥 Team

- **Urooj Waheed** - Project Lead
- **Hackathon 5 Team**

## 🙏 Acknowledgments

- Anthropic for Claude API
- Google for Gemini API
- Groq for fast inference
- Hugging Face for hosting
- Vercel for frontend deployment

## 📞 Support

For support, email urooj@hackathon-5.com or open an issue in the repository.

---

<div align="center">

**Built with ❤️ for Hackathon 5**

[⬆ Back to Top](#flowforge-ai-support)

</div>
