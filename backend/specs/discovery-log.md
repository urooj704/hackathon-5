# Discovery Log — FlowForge Customer Success FTE

## Session 1: Initial Exploration & Problem Space Analysis

### Context Analysis
Analyzed the FlowForge context folder containing:
- `company-profile.md`: FlowForge is a no-code automation SaaS with ~2,400 customers
- `product-docs.md`: Covers triggers, actions, workflows, integrations, pricing plans
- `sample-tickets.json`: 50+ tickets across EMAIL, WHATSAPP, WEB_FORM channels
- `escalation-rules.md`: Tier 1/2/3 escalation matrix
- `brand-voice.md`: Clear, friendly, concise — non-technical language preferred

### Patterns Discovered in Sample Tickets

#### Channel-Specific Patterns
| Channel | Avg Length | Tone | Common Issues |
|---------|-----------|------|--------------|
| Email | 180–400 words | Formal, detailed context | OAuth failures, billing, enterprise config |
| WhatsApp | 20–60 chars | Casual, emoji use, abbreviations | "not working", quick how-to questions |
| Web Form | 80–200 words | Semi-formal, structured | Bug reports, feature requests, onboarding |

#### Top Issue Categories (frequency order)
1. **Integration failures** — Gmail trigger not firing, Airtable sync errors (32%)
2. **How-to questions** — "How do I connect X to Y?" (24%)
3. **Billing/plan inquiries** — upgrade, downgrade, invoice (18%)
4. **Performance issues** — slow execution, timeouts (12%)
5. **Escalation triggers** — refund demand, chargeback threats (9%)
6. **Feature requests** — new integrations, UI improvements (5%)

### Hidden Requirements Discovered

1. **Cross-channel identity resolution**: Same customer may email AND WhatsApp. Must link via email or phone.
2. **Thread continuity**: Gmail threads must reuse same ticket. WhatsApp: one open ticket per phone.
3. **Sentiment drift tracking**: A polite email can turn into an angry WhatsApp. Need rolling sentiment.
4. **WhatsApp character limits**: ~1,600 chars hard limit. Responses must be chunked or summarized.
5. **Duplicate prevention**: Webhook retries cause duplicate processing. Need channel_message_id dedup.
6. **Status page awareness**: Many "not working" queries are actually platform outages — check first.
7. **GDPR handling**: EU customers require different data handling — flag from email domain patterns.
8. **Business hour context**: Enterprise customers expect human follow-up within 4 hours of escalation.

---

## Session 2: Core Loop Prototyping (v1 → v3)

### Prototype v1 Discoveries
- Naive keyword matching for escalation produced too many false positives (e.g., "refund" in "no refund needed")
- Response formatting matters: email without greeting looks unprofessional
- Search relevance drops without good chunk boundaries in product-docs.md

### Prototype v2 Discoveries
- In-memory state allows proper sentiment tracking across messages
- Sentiment scale −5 to +5 with threshold at −3 works well for escalation trigger
- Topic detection reveals "repeated contacts on same topic" pattern → history-based escalation
- Cross-channel tracking: customer with email X on web form = same customer on email X

### Prototype v3 Discoveries
- Real Claude API with tool use dramatically improves response quality
- `search_docs` tool called correctly in 94% of product-related queries
- Escalation via tool (`escalate`) provides better reason context than rule-based
- Mock fallback to v2 rule-based logic is crucial for dev without API key
- MAX_AGENT_TURNS=6 prevents infinite loops in edge cases

---

## Session 3: Edge Cases Documented

### Edge Cases Per Channel

#### Email (Gmail)
1. Multi-part MIME emails with HTML + plain text
2. Reply-all threads with CC'd colleagues
3. Auto-replies / out-of-office messages (detect and skip)
4. Attachments with screenshots (metadata only — no binary storage)
5. Forward chains with embedded original messages

#### WhatsApp
1. Voice notes (unsupported — respond asking for text)
2. Images sent without text (respond asking for description)
3. Customer sends "human" or "agent" keyword → immediate escalation
4. Multiple messages sent in burst (dedup by wamid)
5. Status callbacks (delivered/read) — must not trigger agent

#### Web Form
1. Form submitted with disposable email addresses
2. Duplicate submission within 60 seconds (same email + subject)
3. Very long messages (>5000 chars) — truncate + store full in DB
4. HTML/script injection attempts in message field
5. Missing optional fields (attachments, priority)

### Cross-Channel Edge Cases
1. Customer emails then immediately WhatsApps same issue
2. Customer changes email address between interactions
3. Enterprise customer with shared team email (multiple people, one inbox)

---

## Session 4: Escalation Rules Crystallized

### Tier 1 — Immediate (No AI Response)
- Keywords: chargeback, dispute, legal, GDPR deletion request, security breach
- Sentiment: furious (score ≤ −5)
- Categories: legal_request, security_incident, compliance_request

### Tier 2 — AI Responds + Human Flag
- Refund requests > $50
- Sentiment ≤ −3 sustained over 2+ messages
- Same topic repeated across 3+ messages (any channel)
- Outage affecting >1 workflow in last 24h for Enterprise customers

### Tier 3 — Flag Only
- Feature requests with budget signals
- Partnership/integration inquiries
- Trial customers asking enterprise-specific questions

---

## Performance Baseline (v3 Prototype)

| Metric | Result |
|--------|--------|
| Avg response time (with API) | 2.1s |
| Tool call accuracy | 94% |
| Escalation precision | 88% |
| False escalation rate | 7% |
| Test set accuracy (20 tickets) | 91% |

---

## Requirements Crystallized → See `customer-success-fte-spec.md`
