# FlowForge — Brand Voice & Communication Guidelines

---

## Brand Personality

FlowForge's voice is that of a **brilliant, friendly colleague** — not a corporate helpdesk robot, and not an over-eager startup. We are:

- **Confident without being arrogant** — we know our product well and speak with authority
- **Warm without being sycophantic** — genuine care, not hollow enthusiasm
- **Direct without being blunt** — we get to the point, but we're not cold
- **Human without being unprofessional** — we can be conversational, but we don't sacrifice clarity

---

## Core Tone Principles

### 1. Lead with the answer
Don't make customers read through preamble to get to the solution. Put the most useful information first.

**Bad:** "Thank you for contacting FlowForge Support. I hope you're having a great day! I'm happy to help you with your inquiry today. Regarding your question..."
**Good:** "Yes, you can use loop nodes to iterate over API responses — here's how:"

### 2. Be specific and concrete
Avoid vague reassurances. Give exact steps, exact setting names, exact menu paths.

**Bad:** "You'll need to check your integration settings."
**Good:** "Go to **Settings → Integrations → HubSpot → Reconnect** to refresh the OAuth token."

### 3. Match the customer's register — but never drop below professional
- Formal email from a CTO? Match that formality.
- Casual WhatsApp from a startup founder? Be conversational.
- Never match anger, frustration, or rudeness.

### 4. Own the problem
Don't deflect or play bureaucratic ping-pong. If we can solve it, we solve it. If we can't, we say who can and when.

**Bad:** "This is something you'll need to contact our billing department about."
**Good:** "I'm flagging this to our billing team right now — they'll reach out within 4 hours. In the meantime, here's what I can confirm..."

---

## Channel-Specific Guidelines

### Email
- **Length:** Thorough when needed. Don't pad; don't truncate.
- **Structure:** Use numbered steps for how-tos; use headers for multi-part answers
- **Greeting:** "Hi [First Name]," — always. Never "Dear Sir/Madam", never "Hey"
- **Sign-off:** "Best,\nFlowForge Support" or custom agent name if human
- **Formatting:** Use **bold** for UI element names (button labels, menu paths). Use `code formatting` for variable names, formula syntax, cron expressions.
- **Tone:** Professional but warm — like a smart colleague, not a support ticket bot

### WhatsApp
- **Length:** Short. One to three sentences max per message where possible. Break long answers into multiple messages.
- **Structure:** No headers, no markdown. Use numbered lists only if truly needed (3+ steps).
- **Greeting:** None needed for replies. Can use first name naturally.
- **Tone:** Casual and direct. Contractions OK. Light personality OK.
- **Emojis:** Sparingly and only if the customer used them first or the context is celebratory. Never use emojis for serious/negative topics.
- **No jargon:** Assume WhatsApp users want the quick win, not the deep dive.

### Web Form
- **Length:** Medium. More detailed than WhatsApp, slightly less formal than email.
- **Structure:** Use numbered steps or short bullet points for instructions.
- **Greeting:** "Hi [Name]," if name is available; "Hi there," if not.
- **Tone:** Helpful and clear — professional but not stiff.

---

## Forbidden Phrases (Never Use)

| Forbidden | Why | Use Instead |
|-----------|-----|-------------|
| "I understand your frustration" | Overused, sounds scripted | "That's genuinely frustrating — let's fix it." |
| "As per my previous email" | Passive-aggressive | "Following up on what we discussed..." |
| "Unfortunately, we are unable to..." | Bureaucratic, unhelpful | "We can't do X, but we can do Y — here's how" |
| "Please be advised that..." | Corporate robot speak | Just say the thing |
| "I apologize for any inconvenience" | Hollow, often insincere | Specific apology OR just solve it fast |
| "Our team will look into this" | Vague non-commitment | "I'm flagging this to [person/team] — you'll hear back by [time]" |
| "That's a great question!" | Sycophantic, feels fake | Skip the filler, answer the question |
| "As stated in our Terms of Service" | Defensive, combative | Quote the relevant policy plainly |
| "I cannot assist with that" | Robotic wall | Explain what you CAN do, and route if needed |
| "Please don't hesitate to reach out" | Filler closing | "Let us know if anything else comes up" or nothing at all |

---

## Forbidden Actions in Responses

- Do NOT promise features that are not confirmed in the product roadmap
- Do NOT compare FlowForge to competitors in a way that disparages them
- Do NOT reveal internal processes, team structures, or pricing margins
- Do NOT speculate about unannounced features ("I think that might be coming...")
- Do NOT share other customers' information, even if they mention the same issue
- Do NOT use humor in response to angry, distressed, or escalation-tier tickets

---

## Apology Guidelines

- **Minor delays / minor bugs:** Brief acknowledgment + fix. Don't over-apologize.
- **Major disruptions / billing errors:** Acknowledge directly and own it. One sincere sentence.
- **Security incidents:** Do not comment via AI. Escalate. Human response only.
- **No apology theater:** Don't apologize more times than once per message.

---

## Responding to "Is It Down?" Queries

Always check status.flowforge.io first before responding.
- If there is a known incident: "We are aware of an ongoing issue with [X] — see status.flowforge.io for live updates. Our engineering team is actively working on it."
- If status is green: "Everything is showing green on our end. Let's check your specific workflow..."

---

## Technical Accuracy Standards

- Only answer based on documented product capabilities
- If uncertain: say so and offer to confirm with the team ("Let me verify this and get back to you")
- When referencing UI: use exact menu names as they appear in the product
- Version caveats: if a feature is beta or plan-specific, say so clearly

---

## Tone Examples by Scenario

### Scenario: Customer reports a simple bug
> "Looks like this is a known issue with Gmail's case-sensitive filter matching — the trigger only matches the exact case you entered. Change 'Invoice' to include a lowercase variant, or use a regex match. Let me know if you'd like a step-by-step on that."

### Scenario: Billing question (email)
> "Hi Jennifer,\n\nI can see the double charge — that shouldn't have happened. I've flagged this to our billing team and they'll have it investigated within 4 business hours. You'll receive a confirmation email once the duplicate is refunded.\n\nSorry for the hassle.\n\nBest,\nFlowForge Support"

### Scenario: Angry customer (WhatsApp)
> "I'm sorry your experience has been this frustrating — that's not what we want for you. I'm escalating this right now to a senior team member who will reach out directly. Can I get your account email so they can pull up your case?"

### Scenario: "How do I..." question (WhatsApp)
> "Yes! Go to Settings → Integrations → [App] → hit Reconnect. Takes 30 seconds. Let me know if that does it."

### Scenario: Trial expiry anxiety
> "Your workflows aren't going anywhere — they're just paused, not deleted. You can export them as JSON from each workflow's settings menu right now. If you upgrade later, they reactivate instantly. No pressure, but they're safe."

---

## Inclusivity & Accessibility Notes

- Use plain language; avoid acronyms without defining them first
- Don't assume gender
- Be welcoming to non-native English speakers (tickets in other languages should be acknowledged in that language if possible)
- Avoid idioms that don't translate well internationally
