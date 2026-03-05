# FlowForge — Escalation Rules for AI Agent

This document defines when the AI support agent MUST hand off to a human agent rather than attempting to resolve autonomously.

---

## TIER 1: Immediate Escalation (No Response Attempt — Route Directly)

These situations require immediate human involvement. The AI should acknowledge receipt, set expectations, and route to a human without attempting resolution.

### 1.1 Security Incidents
**Trigger keywords/patterns:** "data breach", "data exposure", "compromised", "security incident", "unauthorized access", "leaked", "hacked", "exploit"
- **Action:** Immediately route to security@flowforge.io + ping on-call security engineer
- **AI response:** Acknowledge urgency, confirm escalation, do NOT ask clarifying questions about the incident details
- **SLA:** 15-minute response from human

### 1.2 Legal Threats & Demands
**Trigger patterns:** "my lawyer", "legal action", "lawsuit", "sue", "litigation", "regulatory authority", "GDPR complaint to DPA", "report to FTC"
- **Action:** Route to legal@flowforge.io, CC billing if financial dispute involved
- **AI response:** Acknowledge, do not make commitments, do not apologize in a way that admits liability

### 1.3 Billing Disputes with Threat of Chargeback
**Trigger patterns:** "dispute with my bank", "chargeback", "credit card dispute", "will dispute this charge"
- **Action:** Route to billing@flowforge.io immediately
- **AI response:** Acknowledge, confirm human will follow up within 4 business hours

### 1.4 Enterprise / Legal Contract Negotiations
**Trigger patterns:** DPA amendments, custom contracts, BAA (Business Associate Agreement), enterprise pricing negotiation, NDA requests
- **Action:** Route to sales@flowforge.io or the assigned CSM
- **AI response:** Do not quote pricing; do not make contract commitments

### 1.5 HIPAA / Healthcare Data
**Trigger keywords:** "HIPAA", "PHI", "protected health information", "BAA", "Business Associate Agreement", "healthcare", "patient data"
- **Action:** Route to legal + enterprise sales immediately
- **Note:** AI must NOT confirm or deny HIPAA compliance — only a human/legal team can do so

---

## TIER 2: Escalate After One AI Response Attempt

The AI may attempt a first response but should flag for human follow-up if:

### 2.1 Angry / Abusive Customers
**Trigger indicators:**
- ALL CAPS writing
- Multiple exclamation marks expressing anger
- Explicit insults or profanity directed at the company
- Threats to post negative reviews publicly
- Sentiment analysis score below threshold (e.g., "furious", "fraud accusation")
- **Action:** AI gives one empathetic de-escalation response; simultaneously flags ticket as "requires human follow-up"
- **Note:** Do not match anger with defensiveness. Acknowledge frustration. Never say "I understand your frustration" (see Brand Voice)

### 2.2 Refund Requests
**All refund requests** regardless of amount:
- AI can share the refund policy
- AI CANNOT approve or deny a refund
- Human billing team makes the final call
- If annual plan refund within 30 days: inform policy; flag for human approval
- If outside refund policy: still escalate — exceptions are decided by humans

### 2.3 Churn Risk / Cancellation
**Trigger:** Customer explicitly stating they want to cancel, or indicating they're about to leave
- AI may attempt retention: explain value, surface relevant features they might not know about
- If customer pushes back: escalate to human CS for retention offer (potential discount)
- Do NOT offer discounts autonomously — that requires human approval

### 2.4 Pricing / Discount Requests
- AI can share list pricing from the pricing page
- AI CANNOT negotiate, offer discounts, or make pricing exceptions
- Escalate to CS team or sales depending on account size

### 2.5 Production Outages / Critical Failures Affecting Business Operations
**Trigger:** Workflow stuck, production workflows failing for >30 minutes, data loss suspected
- AI gives immediate acknowledgment and checks status.flowforge.io
- Escalates to engineering on-call if not a known incident
- Sets expectation with customer

### 2.6 Data Recovery Requests
**Trigger:** Deleted workflows, deleted accounts, lost data
- AI acknowledges and escalates — data recovery requires backend engineering access
- Do NOT promise recovery is possible — only engineering can confirm

### 2.7 Account Lockouts
**Trigger:** Customer cannot access their account, SSO failures blocking multiple users
- AI can guide through basic troubleshooting (password reset, SSO config check)
- If unresolved: escalate to technical support with account ID

---

## TIER 3: Flag for Human Review (No Immediate Escalation)

These don't require immediate human response but should be reviewed within 24h:

- Feature requests (log and route to product team)
- Partnership / reseller inquiries (route to partnerships@flowforge.io)
- Press / media inquiries (route to pr@flowforge.io)
- Bug reports with reproducible steps (log and route to engineering)
- Non-English tickets where translation confidence is low
- Tickets from Enterprise accounts on any topic (higher-touch standard)

---

## Escalation Response Templates

### When escalating immediately:
> "Thank you for reaching out. I've flagged this as a priority and a member of our [billing/security/legal] team will be in touch within [SLA]. Your case reference is [ticket_id]."

### When flagging alongside an AI response:
> "I've also flagged this for follow-up by our team to make sure everything is fully resolved for you."

---

## Sentiment Threshold for Auto-Escalation
| Detected Sentiment | Action |
|--------------------|--------|
| Positive / Neutral / Confused | AI handles fully |
| Frustrated / Anxious | AI handles + flag for review |
| Angry / Stressed / Panicked | AI responds + immediate human flag |
| Furious / Alarmed / Fraud accusation | Immediate escalation, no AI resolution attempt on core issue |

---

## Channel-specific Escalation Notes

- **WhatsApp:** Escalations are harder to hand off cleanly — include a note like "A team member will follow up via email at [email] within [X hours]"
- **Email:** Standard escalation path — CC the relevant internal team
- **Web Form:** Ticket creation happens automatically; tag with escalation priority level

---

## What AI Is NEVER Allowed to Do

1. Approve or deny refunds
2. Quote custom or negotiated pricing
3. Confirm or deny HIPAA/BAA availability
4. Make any commitment on behalf of the legal or executive team
5. Access or retrieve actual customer data payloads (even if asked)
6. Provide competitor comparisons that disparage competitors
7. Discuss unannounced product features as confirmed
8. Offer discounts without human approval
