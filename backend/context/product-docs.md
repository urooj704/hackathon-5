# FlowForge — Product Documentation (Support Knowledge Base)

---

## 1. Getting Started

### 1.1 Creating Your First Workflow
1. Log in → click **"New Workflow"** from the dashboard
2. Choose a **Trigger** (the event that starts the workflow)
3. Add one or more **Actions** (what happens next)
4. Use **Conditions** to branch logic (if/else)
5. Click **Activate** — your workflow is live

**Common triggers:** New email received, Form submitted, Webhook received, Schedule (cron), New row in Google Sheets, Stripe payment succeeded

**Common actions:** Send Slack message, Create HubSpot contact, Add row to Google Sheet, Send HTTP request, Send email via Gmail, Create Notion page

### 1.2 Trial Limitations
- 14-day free trial, no credit card required
- Trial includes all Growth-tier features
- After trial expiry: workflows are paused (not deleted); upgrade to reactivate
- Trial tasks cap: 500 tasks

### 1.3 Connecting Integrations
1. Go to **Settings → Integrations**
2. Click the app you want to connect
3. Authorize via OAuth or enter API key (depends on the service)
4. Connection is account-wide — all team members can use it

**Note:** Some integrations (Salesforce, SAP, Oracle) require Business or Enterprise plan.

---

## 2. Workflow Builder

### 2.1 Triggers
- **Instant triggers:** Webhook, email received, form submission — fire in <1 second
- **Scheduled triggers:** Run at set intervals (every 5 min, hourly, daily, weekly, cron expression)
- **Polling triggers:** For apps without webhooks — FlowForge polls every 1–15 minutes depending on plan

| Plan | Polling Interval |
|------|-----------------|
| Starter | 15 min |
| Growth | 5 min |
| Business | 1 min |
| Enterprise | Real-time |

### 2.2 Actions & Steps
- Each workflow can have unlimited steps (Business+) or up to 10 steps (Starter/Growth)
- **Step types:** Action, Condition (if/else), Loop, Delay, Sub-workflow (Business+), Code step (JS/Python, Enterprise)
- Steps execute sequentially by default; parallel branches available on Business+

### 2.3 Data Transformer
- Map fields between apps using the point-and-click mapper
- Use **Formula Editor** for transformations: `{{upper(first_name)}}`, `{{date_add(created_at, 7, "days")}}`
- Supported types: string, number, boolean, date, array, object, null
- **JSON Path** for nested data: `{{trigger.body.customer.email}}`

### 2.4 Error Handling
- By default, failed steps retry 3× with exponential backoff (1 min, 5 min, 15 min)
- Failed workflows appear in **Workflow History → Failed**
- Each failure shows: error message, step number, raw request/response payload
- **Custom error paths:** Add an "On Error" branch to handle failures gracefully
- **Dead-letter queue:** Failed tasks after all retries → DLQ for manual review

### 2.5 Workflow History & Logs
- All executions logged for 30 days (Starter), 90 days (Growth), 1 year (Business+)
- Access via **Workflow → History** or **Dashboard → Recent Runs**
- Filter by: status (success/failed/running), date range, trigger type
- Download logs as CSV (Business+)

---

## 3. Integrations

### 3.1 Gmail / Google Workspace
- Trigger: New email, New email matching filter, New labeled email
- Action: Send email, Reply to email, Add label, Move to folder, Create draft
- Auth: OAuth 2.0 (connect via "Sign in with Google")
- **Limitation:** Can only send from the connected Gmail address; sending from aliases requires a workaround via SMTP custom action

### 3.2 Slack
- Trigger: New message in channel, New mention, New reaction
- Action: Send message (channel or DM), Update message, Create channel, Invite user
- Auth: OAuth; Slack workspace admin approval may be required
- **Rate limit:** 1 message/second per channel; use Delay node for bulk sends

### 3.3 HubSpot
- Trigger: New contact, Deal stage changed, Form submitted, New deal
- Action: Create/update contact, Create deal, Add note, Send email, Update property
- Auth: OAuth (HubSpot account must be on Professional or above for some triggers)
- **Limitation:** HubSpot sandbox accounts may have API restrictions

### 3.4 Stripe
- Trigger: Payment succeeded, Payment failed, Subscription created/cancelled, Refund created
- Action: Create customer, Create invoice, Create charge (use carefully — irreversible)
- Auth: Stripe API key (Restricted Key recommended — read-only for triggers, write for actions)
- **Important:** FlowForge does NOT process payments; we call Stripe's API. All billing disputes must go through Stripe.

### 3.5 Webhooks (Custom)
- **Incoming webhook:** Every workflow can have a unique URL to receive POST requests
- **Outgoing webhook:** Send HTTP GET/POST/PUT/DELETE/PATCH to any URL
- Supports: custom headers, JSON/form body, query params, basic auth, Bearer token
- Payload size limit: 5MB per request
- **Tip:** Test with Webhook.site or Postman before going live

### 3.6 Google Sheets
- Trigger: New row added, Row updated (polling)
- Action: Add row, Update row, Get row(s), Delete row, Clear sheet
- **Limitation:** Sheets with >500k rows may have performance issues; use Database connector instead

### 3.7 Airtable
- Trigger: New record, Record updated
- Action: Create record, Update record, Find records, Delete record
- Auth: Personal Access Token (not legacy API key — deprecated by Airtable Jan 2024)

---

## 4. Billing & Account Management

### 4.1 Changing Plans
- Upgrades: Immediate effect; prorated charge for remaining billing period
- Downgrades: Take effect at end of current billing cycle
- To change plan: **Settings → Billing → Change Plan**
- Annual ↔ Monthly switches require contacting billing@flowforge.io

### 4.2 Task Usage
- Tasks reset on your billing anniversary date (not calendar month)
- View usage: **Settings → Usage & Billing**
- Overage: $0.002/task for Starter, $0.001/task for Growth, included on Business+
- Usage alerts configurable at 75%, 90%, 100% of limit

### 4.3 Refund Policy
- Free trial: No charge, no refund needed
- Monthly plans: No refunds for partial months (per ToS)
- Annual plans: Prorated refund within 30 days of purchase; no refund after 30 days
- Exceptions reviewed case-by-case — contact billing@flowforge.io

### 4.4 Payment Methods
- Credit/debit card (Visa, Mastercard, Amex, Discover)
- ACH/bank transfer (Business+ annual only)
- Invoice/PO (Enterprise only)
- No PayPal, crypto, or wire transfer

### 4.5 Invoices & Receipts
- Auto-emailed after each charge to the billing email
- Download past invoices: **Settings → Billing → Invoice History**
- Update billing email: **Settings → Billing → Billing Contact**

---

## 5. Team & Workspace (Business+)

### 5.1 Inviting Team Members
- **Settings → Team → Invite Member** → enter email → choose role
- Roles: **Owner** (full access), **Admin** (all except billing/delete workspace), **Editor** (create/edit workflows), **Viewer** (read-only)
- Invites expire after 7 days; resend via Settings → Team

### 5.2 SSO (SAML 2.0)
- Available on Business and Enterprise plans
- Supported providers: Okta, Azure AD, Google Workspace, OneLogin
- Setup: **Settings → Security → SSO** — follow the SAML config guide
- **Important:** After SSO is enabled, all users must log in via SSO (password login disabled)

### 5.3 Audit Logs
- Available Business+ — track all admin actions, workflow changes, member activity
- Export as CSV; 1-year retention

---

## 6. FlowForge AI (Beta)

### 6.1 What It Can Do
- **Natural language → workflow:** Describe what you want; AI builds the scaffold
- **Smart field suggestions:** AI suggests mappings based on field names
- **Workflow summarization:** Explains what an existing complex workflow does
- **Anomaly detection (coming soon):** Alert when workflow behavior deviates from baseline

### 6.2 Current Limitations
- AI-generated workflows must be reviewed before activating — not production-ready out of the box
- Supports ~80 integrations (not all 300+)
- Beta: may produce incorrect mappings; always test in sandbox first
- Not available on Starter plan

### 6.3 Enabling FlowForge AI
- Growth+: Go to **Settings → Features → FlowForge AI → Enable Beta**
- Feedback button in every AI-generated workflow appreciated

---

## 7. Security & Compliance

### 7.1 Data Handling
- Customer workflow data (triggers/payloads) stored for log retention period only
- FlowForge employees do NOT have access to payload contents (zero-knowledge design)
- Data processing: AWS us-east-1 (default), eu-west-1 (EU residency, Business+)

### 7.2 Credentials Storage
- OAuth tokens encrypted at rest (AES-256) and never exposed via API
- API keys stored as encrypted secrets; displayed once on creation
- If a credential is compromised: revoke in the source app first, then reconnect in FlowForge

### 7.3 IP Allowlisting
- FlowForge outbound IPs (static): 34.201.xx.xx range — see docs.flowforge.io/ips
- Inbound webhook IPs: same range
- For Enterprise: dedicated IP available on request

---

## 8. Common Errors & Troubleshooting

### 8.1 "Authentication Failed" / "401 Unauthorized"
- **Cause:** OAuth token expired or revoked; API key rotated
- **Fix:** Go to Settings → Integrations → [App] → Reconnect

### 8.2 "Rate Limit Exceeded" (429 error)
- **Cause:** Workflow is sending requests faster than the target app allows
- **Fix:** Add a Delay node (1–2 seconds between iterations); reduce trigger frequency

### 8.3 Workflow Not Triggering
- Check if workflow is **Active** (toggle on dashboard)
- Check trigger configuration — verify the right account/folder/filter is selected
- Check Workflow History for any error state
- For polling triggers: wait up to 1 polling cycle; check if plan allows the polling interval you configured

### 8.4 "Payload Too Large" (413 error)
- **Cause:** Incoming webhook payload >5MB
- **Fix:** Split the data at the source; send in batches

### 8.5 Missing Data in Action
- Use **Test Step** feature to inspect exactly what data is available at each step
- Verify the trigger fired with expected data — check History for the actual payload
- Use optional chaining in formulas: `{{trigger.body.customer?.email}}` to handle missing fields

### 8.6 Workflow Stuck in "Running"
- Rare but possible if an external API hangs
- Workflows auto-timeout after 30 minutes (Business) / 10 minutes (Starter/Growth)
- Contact support if a workflow is stuck longer than expected

---

## 9. Limits & Quotas (Summary)

| Feature | Starter | Growth | Business | Enterprise |
|---------|---------|--------|----------|------------|
| Active workflows | 5 | 25 | Unlimited | Unlimited |
| Tasks/month | 1,000 | 10,000 | 100,000 | Custom |
| Steps per workflow | 10 | 10 | Unlimited | Unlimited |
| Polling interval | 15 min | 5 min | 1 min | Real-time |
| Log retention | 30 days | 90 days | 1 year | Custom |
| Team members | 1 | 5 | 20 | Unlimited |
| Custom webhooks | ✓ | ✓ | ✓ | ✓ |
| Sub-workflows | ✗ | ✗ | ✓ | ✓ |
| Code steps | ✗ | ✗ | ✗ | ✓ |
| SSO | ✗ | ✗ | ✓ | ✓ |
| EU data residency | ✗ | ✗ | ✓ | ✓ |
| SLA | ✗ | ✗ | 4h | 2h |

---

## 10. FAQ — Quick Reference

**Q: Can I use FlowForge for free?**
A: Yes, 14-day trial (Growth features). No credit card required.

**Q: What happens to my workflows if I downgrade?**
A: If you have more active workflows than your new plan allows, the excess are paused (not deleted). You choose which to keep active.

**Q: Can I export my workflows?**
A: Yes — each workflow can be exported as JSON from the workflow settings menu. Re-import in the same or another account.

**Q: Is there a free plan?**
A: No permanent free plan currently. Trial only.

**Q: Can FlowForge trigger on inbound SMS?**
A: Via Twilio integration — receive SMS → webhook → trigger workflow. Requires Twilio account.

**Q: Does FlowForge support branching/conditional logic?**
A: Yes — Condition nodes support if/else, switch, and custom JavaScript expressions (Business+).

**Q: Can I run workflows manually?**
A: Yes — click "Run Now" from the workflow detail page. Useful for testing or one-off runs.

**Q: What's the uptime SLA?**
A: 99.9% uptime on Business+. Historical uptime visible at status.flowforge.io.
