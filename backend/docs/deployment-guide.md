# Deployment Guide — FlowForge Customer Success FTE

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Application runtime |
| Docker | 24+ | Container build |
| kubectl | 1.28+ | Kubernetes management |
| minikube/k3s | Latest | Local Kubernetes (dev) |
| PostgreSQL | 16 with pgvector | Database |
| Apache Kafka | 3.6+ | Message streaming |
| Redis | 7+ | Cache / session |

---

## Environment Setup

### 1. Clone & Configure

```bash
git clone <repo-url>
cd hackaton-5
cp .env.example .env
```

Edit `.env` with your API keys:

```env
# AI
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Database
DATABASE_URL=postgresql+asyncpg://fte_user:password@localhost:5432/fte_db
DATABASE_URL_SYNC=postgresql://fte_user:password@localhost:5432/fte_db

# Redis
REDIS_URL=redis://localhost:6379/0

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Gmail
GMAIL_CLIENT_ID=...
GMAIL_CLIENT_SECRET=...
GMAIL_REFRESH_TOKEN=...
GMAIL_FROM_EMAIL=support@yourcompany.com

# WhatsApp (Meta Cloud API)
WHATSAPP_PHONE_NUMBER_ID=...
WHATSAPP_ACCESS_TOKEN=...
WHATSAPP_VERIFY_TOKEN=your-random-verify-token
```

---

## Local Development

### Start infrastructure

```bash
docker-compose up -d    # Starts PostgreSQL + Redis + Kafka (if configured)
```

### Apply database migrations

```bash
alembic upgrade head
```

### Start the API server

```bash
uvicorn src.app:app --reload --port 8000
```

### Start the message processor worker

```bash
python workers/message_processor.py
```

### Start the MCP server (for Claude Desktop)

```bash
python mcp_server.py
```

### Start the web form (Next.js)

```bash
cd web-form
npm install
npm run dev     # Runs on http://localhost:3001
```

---

## Docker Build

```bash
# Build image
docker build -t your-registry/customer-success-fte:latest .

# Push to registry
docker push your-registry/customer-success-fte:latest
```

### Dockerfile (add to project root if not present)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Kubernetes Deployment

### 1. Create namespace

```bash
kubectl apply -f k8s/namespace.yaml
```

### 2. Apply ConfigMap

```bash
kubectl apply -f k8s/configmap.yaml
```

### 3. Create secrets

```bash
# Method A: From file
kubectl create secret generic fte-secrets \
  --from-env-file=.env \
  --namespace=customer-success-fte

# Method B: From YAML (fill in secrets.yaml first)
# kubectl apply -f k8s/secrets.yaml
```

### 4. Deploy PostgreSQL

```bash
kubectl apply -f k8s/postgres.yaml
kubectl wait --for=condition=ready pod -l app=postgres -n customer-success-fte --timeout=120s
```

### 5. Run database migrations

```bash
kubectl run alembic-migrate \
  --image=your-registry/customer-success-fte:latest \
  --restart=Never \
  --namespace=customer-success-fte \
  --env-from=configmap/fte-config \
  --env-from=secret/fte-secrets \
  -- alembic upgrade head
```

### 6. Deploy API + Worker

```bash
kubectl apply -f k8s/deployment-api.yaml
kubectl apply -f k8s/deployment-worker.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
kubectl apply -f k8s/hpa.yaml
```

### 7. Verify deployment

```bash
kubectl get pods -n customer-success-fte
kubectl get svc -n customer-success-fte
kubectl get ingress -n customer-success-fte

# Check logs
kubectl logs -l component=api -n customer-success-fte --tail=50
kubectl logs -l component=message-processor -n customer-success-fte --tail=50
```

---

## Channel Configuration

### Gmail

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create OAuth 2.0 credentials (Desktop App type)
3. Enable Gmail API
4. Set up Pub/Sub topic and subscription
5. Register webhook: `POST https://support-api.flowforge.io/channels/gmail/webhook`

### WhatsApp (Meta Cloud API)

1. Create a Meta Business account
2. Set up a WhatsApp Business App in Meta Developer Portal
3. Configure webhook URL: `https://support-api.flowforge.io/channels/whatsapp/webhook`
4. Set verify token to match `WHATSAPP_VERIFY_TOKEN` in your secrets

### Web Form

Embed in your website:

```html
<script src="https://cdn.flowforge.io/support-form.js"></script>
<div id="support-form"></div>
<script>
  FlowForgeSupport.init({
    container: '#support-form',
    apiEndpoint: 'https://support-api.flowforge.io/channels/web-form/submit'
  });
</script>
```

Or use the React component directly:

```jsx
import SupportForm from './web-form/SupportForm';

export default function SupportPage() {
  return (
    <SupportForm
      apiEndpoint="https://support-api.flowforge.io/channels/web-form/submit"
    />
  );
}
```

---

## Running Tests

```bash
# Unit tests
pytest tests/ -v --ignore=tests/test_multichannel_e2e.py --ignore=tests/load_test.py

# E2E tests (requires running API server)
uvicorn src.app:app --port 8000 &
pytest tests/test_multichannel_e2e.py -v

# Load tests (requires Locust)
pip install locust
locust -f tests/load_test.py --host=http://localhost:8000 --users 10 --spawn-rate 2 --run-time 5m --headless
```

---

## Knowledge Base Update

To re-index product documentation:

```bash
# Delete existing chunks (will trigger re-index on next startup)
psql $DATABASE_URL -c "DELETE FROM doc_chunks;"

# Restart API (triggers load_knowledge_base())
kubectl rollout restart deployment/fte-api -n customer-success-fte
```

---

## Monitoring

Key metrics to watch:
- `P95 response latency < 3000ms` — SLA target
- `Uptime > 99.9%` — availability target
- `Escalation rate < 25%` — quality target
- `Message loss rate = 0%` — reliability target

```bash
# View real-time metrics
kubectl top pods -n customer-success-fte

# API metrics endpoint
curl https://support-api.flowforge.io/metrics/channels
```
