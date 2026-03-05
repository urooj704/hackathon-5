# Customer Success FTE Specification
## FlowForge AI Agent — Production Specification

---

## Purpose
Handle routine customer support queries with speed, consistency, and empathy across
multiple communication channels — 24/7, without breaks, sick days, or management overhead.

**Cost target**: < $1,000/year operating cost vs $75,000+ human FTE
**Availability target**: 99.9% uptime
**Response SLA**: P95 < 3 seconds

---

## Supported Channels

| Channel | Identifier | Response Style | Max Length | Integration |
|---------|-----------|----------------|------------|-------------|
| Email (Gmail) | Email address | Formal, detailed | 500 words | Gmail API + Pub/Sub |
| WhatsApp | Phone (E.164) | Conversational, concise | 1,600 chars | Meta Cloud API |
| Web Form | Email address | Semi-formal | 300 words | FastAPI REST |

---

## Scope

### In Scope
- Product feature questions and how-to guidance
- Bug report intake and triage
- Billing inquiry intake (NOT negotiation)
- Workflow / integration troubleshooting
- Status page checks for outage-related queries
- Feedback collection
- Cross-channel conversation continuity
- Sentiment monitoring with escalation triggers

### Out of Scope (Escalate)
- Pricing negotiations and custom contract terms
- Refund processing (intake only, escalate immediately)
- Legal/compliance document requests
- Security incident response
- Customers with sustained negative sentiment (score ≤ −3)
- Chargeback disputes

---

## Tools

| Tool | Purpose | Constraints |
|------|---------|-------------|
| `search_docs` | Semantic search over product knowledge base | Max 5 results per call |
| `create_ticket` | Create support ticket with channel metadata | Call at start of every new issue |
| `update_ticket` | Update ticket status/urgency/summary | Use after resolution or status change |
| `escalate` | Route to human agent (Tier 1/2/3) | Log reason + keywords |
| `check_status_page` | Check active platform incidents | Always use for "not working" reports |
| `get_customer_history` | Retrieve cross-channel history | Use to detect repeat contacts |

---

## Agent Skills

### 1. Knowledge Retrieval Skill
- **Trigger**: Customer asks any product/technical question
- **Input**: Query text (raw customer language, not reformatted)
- **Process**: Generate embedding → cosine search → return top 5 chunks
- **Output**: Relevant doc snippets with section titles
- **Fallback**: If no results (score < 0.7), respond "I'll need to check on that"

### 2. Sentiment Analysis Skill
- **Trigger**: Every inbound customer message
- **Input**: Message text
- **Process**: Score −5 to +5; map to label (furious/angry/frustrated/neutral/positive)
- **Output**: Score + label + confidence
- **Escalation**: Score ≤ −3 → Tier 2; score ≤ −5 → Tier 1

### 3. Escalation Decision Skill
- **Trigger**: After every agent response
- **Input**: Current ticket context, sentiment trend, message content
- **Keyword triggers**: chargeback, refund, legal, GDPR, breach, cancel, lawyer, sue
- **History trigger**: Same topic in 3+ contacts across any channel
- **Output**: `should_escalate` (bool), `tier` (1/2/3), `reason` (text), `route_to` (team)

### 4. Channel Adaptation Skill
- **Trigger**: Before every outbound message
- **Input**: Response text, target channel
- **Email**: Add formal greeting + signature + ticket reference
- **WhatsApp**: Truncate to 1,600 chars, use emojis sparingly, add "Reply for more help"
- **Web Form**: Semi-formal, include ticket ID, offer follow-up option
- **Output**: Channel-formatted response text

### 5. Customer Identification Skill
- **Trigger**: On every inbound message
- **Input**: Message metadata (email, phone number, name)
- **Lookup chain**: Email → Phone → Create new
- **Output**: Unified `customer_id` + merged cross-channel history
- **Cross-channel linking**: WhatsApp phone matched to email from previous web form ticket

---

## Database Schema

```
customers        — unified identity record (email | phone)
tickets          — one ticket per issue, tracks origin_channel
messages         — individual messages (any channel, any direction)
escalations      — escalation events with tier + routing
doc_chunks       — knowledge base with pgvector embeddings
```

---

## Queue Architecture

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Message Queue | Apache Kafka | Inbound messages from all channels |
| Worker | Python asyncio | Process messages, run agent |
| Dead Letter Queue | Kafka DLQ topic | Failed messages for human review |
| Cache | Redis | Rate limiting, session state |

---

## Escalation Matrix

| Trigger | Tier | Response | Route To |
|---------|------|----------|---------|
| Chargeback / dispute | Tier 1 | No AI response | billing@flowforge.io |
| Legal / GDPR | Tier 1 | No AI response | legal@flowforge.io |
| Security incident | Tier 1 | No AI response | security@flowforge.io |
| Sentiment ≤ −5 (furious) | Tier 1 | No AI response | human_queue |
| Refund request | Tier 2 | AI response + flag | billing@flowforge.io |
| Sentiment ≤ −3 | Tier 2 | AI response + flag | human_queue |
| Data loss report | Tier 2 | AI response + flag | engineering_oncall |
| Repeat contact (3x same topic) | Tier 2 | AI response + flag | human_queue |
| Feature request | Tier 3 | AI response | human_queue |
| Partnership inquiry | Tier 3 | AI response | partnerships@flowforge.io |

---

## Channel-Specific Response Templates

### Email Template
```
Dear {customer_name},

Thank you for reaching out to FlowForge Support.

{response_body}

If you need further assistance, simply reply to this email.

Best regards,
FlowForge AI Support Team
Ticket Reference: {display_id}
---
This response was generated by our AI assistant.
For complex issues, a human agent will follow up.
```

### WhatsApp Template
```
{response_body}

📱 Reply to continue or type *human* for live support.
Ref: {display_id}
```

### Web Form Template
```
{response_body}

---
Your ticket ID: {display_id}
Need more help? Reply to this email or visit support.flowforge.io
```

---

## Performance Targets

| Metric | Target |
|--------|--------|
| Response latency P95 | < 3 seconds |
| Uptime | > 99.9% |
| Escalation rate | < 25% |
| Cross-channel customer match rate | > 95% |
| Message loss rate | 0% |
| False escalation rate | < 10% |

---

## Deployment Architecture

- **API Layer**: FastAPI, 3 replicas minimum (HPA: 3–20)
- **Worker Layer**: Kafka consumer, 3 replicas minimum (HPA: 3–30)
- **Database**: PostgreSQL 16 with pgvector extension
- **Cache/Queue**: Redis (session) + Kafka (messages)
- **Container**: Docker, deployed on Kubernetes
- **Ingress**: nginx with TLS (cert-manager)

---

*Specification version: 1.0 — Crystallized from incubation phase discovery*
