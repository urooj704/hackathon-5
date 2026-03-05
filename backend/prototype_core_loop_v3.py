"""
FlowForge Customer Success Agent -- Prototype Core Loop v3
==========================================================
Exercise 1.4: Replace rule-based response generation with real Claude API calls.

NEW in v3:
  - Real Claude API  (claude-haiku-4-5-20251001, sync client)
  - Tool use         search_docs(query) + escalate(tier, reason, route_to)
  - Agentic loop     up to MAX_AGENT_TURNS turns per message
  - System prompt    injects customer context + history + channel rules
  - Mock mode        falls back to v2 rule-based when ANTHROPIC_API_KEY not set

Setup:
  pip install anthropic          (already in requirements.txt)
  export ANTHROPIC_API_KEY=sk-ant-...
  -- OR --  add  ANTHROPIC_API_KEY=sk-ant-...  to .env in project root

Run:  python prototype_core_loop_v3.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

# Force UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Load .env if present (soft dependency)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ==============================================================================
# 0. CONSTANTS & CONFIG
# ==============================================================================

DOCS_PATH        = Path(__file__).parent / "context" / "product-docs.md"
WHATSAPP_MAX_CHARS = 280
SEARCH_TOP_K     = 3
SEARCH_MIN_SCORE = 1

# v2 thresholds (still used for pre-checks and mock mode)
SENTIMENT_ESCALATE_SCORE   = -3
REPEAT_ISSUE_MSG_THRESHOLD = 2

# v3 Claude config
CLAUDE_MODEL     = "claude-haiku-4-5-20251001"
MAX_AGENT_TURNS  = 6

# Detect whether Claude is available
try:
    import anthropic as _anthropic_module
    _ANTHROPIC_PKG = True
except ImportError:
    _ANTHROPIC_PKG = False

USE_CLAUDE = _ANTHROPIC_PKG and bool(os.getenv("ANTHROPIC_API_KEY"))

STOP_WORDS = {
    "i", "my", "me", "we", "you", "your", "it", "is", "am", "are", "was",
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "this", "that", "have", "has", "had", "do", "does", "did",
    "be", "been", "can", "will", "would", "could", "should", "not", "no",
    "hi", "hello", "hey", "dear", "regards", "thanks", "thank", "please",
    "need", "help", "how", "what", "when", "why", "where", "get", "want",
    "just", "also", "if", "so", "about", "our", "us", "from", "im", "its",
    "still", "now", "again", "back", "tried", "thing",
}


# ==============================================================================
# 1. ENUMS & DATA STRUCTURES
# ==============================================================================

class Channel(Enum):
    EMAIL    = "email"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"


class EscalationTier(Enum):
    NONE  = "none"
    TIER1 = "tier_1"
    TIER2 = "tier_2"
    TIER3 = "tier_3"


class ResolutionStatus(Enum):
    OPEN      = "open"
    SOLVED    = "solved"
    ESCALATED = "escalated"


@dataclass
class InboundMessage:
    channel:      Channel
    body:         str
    sender_email: Optional[str] = None
    sender_name:  Optional[str] = None
    sender_phone: Optional[str] = None


@dataclass
class DocSection:
    title:   str
    content: str
    score:   int = 0


@dataclass
class EscalationResult:
    tier:         EscalationTier
    reason:       str  = ""
    route:        str  = ""
    keywords_hit: list = field(default_factory=list)
    source:       str  = "rule"   # "rule" | "history" | "sentiment" | "claude" | "pre_check"

    @property
    def should_escalate(self) -> bool:
        return self.tier != EscalationTier.NONE


@dataclass
class HistoryEntry:
    role:      str
    body:      str
    channel:   Channel
    timestamp: str
    topics:    list = field(default_factory=list)


@dataclass
class AgentTurn:
    """One turn of the Claude agentic loop. NEW in v3."""
    turn_num:    int
    action:      str                    # "tool_use" | "end_turn" | "mock" | "pre_check"
    tool_name:   Optional[str]  = None
    tool_input:  Optional[dict] = None
    tool_result: Optional[str]  = None  # truncated preview
    text:        Optional[str]  = None  # final response text (end_turn only)


@dataclass
class ConversationState:
    customer_id:       str
    customer_name:     Optional[str]
    emails:            set
    phones:            set
    history:           list
    sentiment_score:   int
    topics:            list
    resolution_status: ResolutionStatus
    original_channel:  Channel
    channels_used:     list
    escalation_tier:   Optional[EscalationTier]
    message_count:     int

    @property
    def sentiment_label(self) -> str:
        if self.sentiment_score >= 2:   return "positive"
        if self.sentiment_score >= -1:  return "neutral"
        if self.sentiment_score >= -3:  return "negative"
        return "very_negative"

    @property
    def is_returning(self) -> bool:
        return self.message_count >= 1


@dataclass
class PipelineResult:
    channel:              Channel
    customer_id:          str
    is_returning:         bool
    original_body:        str
    normalized_text:      str
    query_words:          list
    matched_sections:     list        # pre-search results (still done for context)
    escalation:           EscalationResult
    response:             str
    state_snapshot:       ConversationState
    message_topics:       list
    prev_sentiment_score: int
    agent_turns:          list        # list[AgentTurn]  NEW in v3
    mode:                 str         # "live" | "mock" | "pre_check"  NEW in v3


# ==============================================================================
# 2. IN-MEMORY CUSTOMER STORE  (unchanged from v2)
# ==============================================================================

_CUSTOMER_STORE: dict[str, ConversationState] = {}
_EMAIL_INDEX:    dict[str, str] = {}
_PHONE_INDEX:    dict[str, str] = {}
_ID_COUNTER:     list[int]      = [0]


def _next_customer_id() -> str:
    _ID_COUNTER[0] += 1
    return f"CUST-{_ID_COUNTER[0]:04d}"


def resolve_customer_id(email, phone, name, channel):
    cid = None
    if email and email.lower() in _EMAIL_INDEX:
        cid = _EMAIL_INDEX[email.lower()]
    if cid is None and phone and phone in _PHONE_INDEX:
        cid = _PHONE_INDEX[phone]
    if cid is None:
        cid = _next_customer_id()
        _CUSTOMER_STORE[cid] = ConversationState(
            customer_id=cid, customer_name=name,
            emails=set(), phones=set(), history=[],
            sentiment_score=0, topics=[],
            resolution_status=ResolutionStatus.OPEN,
            original_channel=channel, channels_used=[],
            escalation_tier=None, message_count=0,
        )
    state = _CUSTOMER_STORE[cid]
    if name and not state.customer_name:
        state.customer_name = name
    if email:
        _EMAIL_INDEX[email.lower()] = cid
        state.emails.add(email.lower())
    if phone:
        _PHONE_INDEX[phone] = cid
        state.phones.add(phone)
    if channel not in state.channels_used:
        state.channels_used.append(channel)
    return cid


def get_state(cid):
    return _CUSTOMER_STORE[cid]


# ==============================================================================
# 3. SENTIMENT & TOPICS  (unchanged from v2)
# ==============================================================================

_POSITIVE_WORDS = {
    "thanks","thank","great","excellent","perfect","love","wonderful","awesome",
    "helpful","resolved","fixed","working","brilliant","solved","appreciate",
    "amazing","fantastic","happy",
}
_NEGATIVE_WORDS = {
    "broken","error","issue","problem","failed","failing","frustrated","angry",
    "disappointed","wrong","terrible","awful","ridiculous","unacceptable",
    "horrible","joke","useless","garbage",
}
_VERY_NEGATIVE_WORDS = {
    "unacceptable","fraud","scam","garbage","useless","worst",
    "rip off","ripped off","absolutely terrible","total garbage",
}
_STILL_BROKEN_PHRASES = [
    "still not working","still broken","still failing","didn't fix","not fixed",
    "same issue","same error","same problem","still having trouble",
]


def update_sentiment(text: str, current_score: int) -> int:
    lower = text.lower()
    delta = 0
    for w in _POSITIVE_WORDS:
        if w in lower: delta += 1
    for w in _NEGATIVE_WORDS:
        if w in lower: delta -= 1
    for w in _VERY_NEGATIVE_WORDS:
        if w in lower: delta -= 1
    for phrase in _STILL_BROKEN_PHRASES:
        if phrase in lower:
            delta -= 2
            break
    return max(-5, min(5, current_score + delta))


_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "authentication":   ["401","unauthorized","token","reconnect","oauth","credentials","login","403","auth"],
    "billing":          ["invoice","charge","payment","billing","charged","subscription","cost","price","199","99"],
    "plan_change":      ["upgrade","downgrade","plan","business plan","growth plan","starter","tier"],
    "workflow_trigger": ["trigger","triggering","not firing","automation","workflow","not running","isn't triggering"],
    "integration":      ["hubspot","airtable","slack","stripe","gmail","integration","connect","webhook"],
    "rate_limit":       ["429","rate limit","too many requests","throttle"],
    "legal":            ["lawyer","legal","sue","lawsuit","litigation"],
    "data_loss":        ["deleted","lost","missing","disappeared","gone"],
    "performance":      ["slow","timeout","delay","hanging","stuck"],
    "team_management":  ["team","invite","member","role","permission","sso"],
    "refund":           ["refund","money back","reimburse","reimbursement"],
    "cancellation":     ["cancel","cancellation","leaving","switching to","closing my account"],
}


def extract_topics(text: str) -> list[str]:
    lower = text.lower()
    return [t for t, kws in _TOPIC_KEYWORDS.items() if any(kw in lower for kw in kws)]


def merge_topics(existing: list[str], new_topics: list[str]) -> list[str]:
    result = list(existing)
    for t in new_topics:
        if t not in result:
            result.append(t)
    return result


# ==============================================================================
# 4. KB LOADER, NORMALIZE, SEARCH  (unchanged from v2)
# ==============================================================================

def load_knowledge_base(path: Path = DOCS_PATH) -> list[DocSection]:
    if not path.exists():
        print(f"[WARN] docs not found at {path}")
        return []
    raw = path.read_text(encoding="utf-8")
    matches = list(re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE).finditer(raw))
    sections = []
    for i, m in enumerate(matches):
        title = m.group(2).strip()
        start = m.end()
        end   = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        body  = raw[start:end].strip()
        if body:
            sections.append(DocSection(title=title, content=body))
    return sections


def normalize(msg: InboundMessage) -> str:
    text  = msg.body
    lines = [l for l in text.splitlines() if not l.strip().startswith(">")]
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def extract_query_words(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return list({w for w in words if w not in STOP_WORDS and len(w) > 2})


def search_docs(query_words: list[str], kb: list[DocSection], top_k=SEARCH_TOP_K) -> list[DocSection]:
    results = []
    for sec in kb:
        score = sum(3 if w in sec.title.lower() else 1 for w in query_words if w in sec.content.lower() or w in sec.title.lower())
        if score >= SEARCH_MIN_SCORE:
            results.append(DocSection(title=sec.title, content=sec.content, score=score))
    results.sort(key=lambda s: s.score, reverse=True)
    return results[:top_k]


# ==============================================================================
# 5. ESCALATION RULES  (unchanged from v2)
# ==============================================================================

_ESCALATION_RULES = [
    (["my lawyer","legal action","lawsuit","sue you","i will sue","litigation","report to ftc","gdpr complaint"],
     EscalationTier.TIER1, "Legal threat or regulatory complaint", "legal@flowforge.io"),
    (["data breach","security incident","unauthorized access","leaked data","been hacked","exploit"],
     EscalationTier.TIER1, "Potential security incident", "security@flowforge.io"),
    (["chargeback","dispute with my bank","credit card dispute","will dispute this charge"],
     EscalationTier.TIER1, "Chargeback threat", "billing@flowforge.io"),
    (["hipaa","phi","protected health information","baa","business associate agreement"],
     EscalationTier.TIER1, "HIPAA / healthcare data question", "legal@flowforge.io"),
    (["refund","money back","want my money","reimburse","reimbursement"],
     EscalationTier.TIER2, "Refund request", "billing@flowforge.io"),
    (["cancel my account","cancellation","want to cancel","switching to zapier","switch to zapier","leaving flowforge","closing my account"],
     EscalationTier.TIER2, "Cancellation threat", "human_queue"),
    (["give me a discount","cheaper plan","negotiate price","pricing negotiation","custom pricing"],
     EscalationTier.TIER2, "Pricing negotiation", "sales@flowforge.io"),
    (["this is ridiculous","this is unacceptable","absolutely terrible","worst service","totally useless","total garbage","fraud","scam","rip off"],
     EscalationTier.TIER2, "Angry/frustrated customer", "human_queue"),
    (["feature request","please add","suggestion for","feature idea","would be great if"],
     EscalationTier.TIER3, "Feature request", "product_team"),
    (["partner with","reseller","partnership inquiry","affiliate program"],
     EscalationTier.TIER3, "Partnership inquiry", "partnerships@flowforge.io"),
]
_PROFANITY = {"damn","hell","crap","shit","fuck","ass","bastard","idiot"}


def check_escalation(text: str) -> EscalationResult:
    lower = text.lower()
    for phrases, tier, reason, route in _ESCALATION_RULES:
        hits = [p for p in phrases if p in lower]
        if hits:
            return EscalationResult(tier=tier, reason=reason, route=route, keywords_hit=hits, source="rule")
    caps_run = 0
    for w in text.split():
        if re.fullmatch(r"[A-Z]{3,}[!?]*", w):
            caps_run += 1
            if caps_run >= 3:
                return EscalationResult(tier=EscalationTier.TIER2, reason="ALL CAPS message", route="human_queue", keywords_hit=["ALL_CAPS"], source="rule")
        else:
            caps_run = 0
    found = set(re.findall(r"[a-z]+", lower)) & _PROFANITY
    if found:
        return EscalationResult(tier=EscalationTier.TIER2, reason="Strong language", route="human_queue", keywords_hit=list(found), source="rule")
    return EscalationResult(tier=EscalationTier.NONE)


def check_history_escalation(state: ConversationState, current_topics: list[str]) -> Optional[EscalationResult]:
    if state.sentiment_score <= SENTIMENT_ESCALATE_SCORE:
        return EscalationResult(
            tier=EscalationTier.TIER2,
            reason=f"Accumulated frustration (score: {state.sentiment_score})",
            route="human_queue",
            keywords_hit=[f"sentiment={state.sentiment_score}"],
            source="sentiment",
        )
    if state.message_count >= REPEAT_ISSUE_MSG_THRESHOLD:
        overlap = [t for t in current_topics if t in state.topics]
        if overlap:
            return EscalationResult(
                tier=EscalationTier.TIER2,
                reason=f"Persistent issue after {state.message_count} messages: {', '.join(overlap)}",
                route="human_queue",
                keywords_hit=[f"repeat:{t}" for t in overlap],
                source="history",
            )
    return None


def _merge_escalations(a: EscalationResult, b: Optional[EscalationResult]) -> EscalationResult:
    if b is None:
        return a
    pri = {EscalationTier.TIER1: 3, EscalationTier.TIER2: 2, EscalationTier.TIER3: 1, EscalationTier.NONE: 0}
    return b if pri[b.tier] > pri[a.tier] else a


# ==============================================================================
# 6. SYSTEM PROMPT BUILDER  (NEW in v3)
# ==============================================================================

_CHANNEL_FORMAT_RULES = {
    Channel.EMAIL: (
        "Email format:\n"
        "  - First line must be: Hi [Customer first name],\n"
        "  - Blank line after greeting\n"
        "  - Use markdown bullet lists for steps\n"
        "  - End with exactly two lines: Best,\\nFlowForge Support"
    ),
    Channel.WHATSAPP: (
        "WhatsApp format:\n"
        "  - No formal greeting or sign-off\n"
        "  - Plain text only -- no markdown, no ** bold, no ## headings\n"
        "  - Maximum 3 short sentences total\n"
        "  - Casual, direct tone"
    ),
    Channel.WEB_FORM: (
        "Web Form format:\n"
        "  - First line must be: Hi [Customer first name],\n"
        "  - Blank line after greeting\n"
        "  - Semi-formal tone\n"
        "  - No sign-off needed"
    ),
}


def build_system_prompt(state: ConversationState, channel: Channel) -> str:
    """Build the Claude system prompt with customer context + history + channel rules."""
    name       = state.customer_name or "the customer"
    first_name = name.split()[0]
    contact    = ", ".join(state.emails) or ", ".join(state.phones) or "(unknown)"

    # Conversation history (last 6 entries = 3 pairs)
    hist_entries = state.history[-6:] if state.history else []
    if hist_entries:
        hist_lines = []
        for e in hist_entries:
            role_tag = "CUSTOMER" if e.role == "user" else "AGENT"
            preview  = e.body[:200].replace("\n", " ").strip()
            hist_lines.append(f"  {role_tag} [{e.channel.value}]: {preview}")
        history_block = "\n".join(hist_lines)
    else:
        history_block = "  (No prior conversation -- this is the first message)"

    # Alerts
    alerts = []
    if state.sentiment_score <= -2:
        alerts.append(
            f"[!] Customer is frustrated (sentiment score: {state.sentiment_score}). "
            "Show empathy and resolve quickly or escalate."
        )
    if state.message_count >= 2:
        repeat = ", ".join(state.topics[:3])
        alerts.append(
            f"[!] Returning customer -- {state.message_count} prior messages about: {repeat}. "
            "If the issue is unresolved, escalate rather than repeat the same suggestions."
        )
    alert_block = "\n".join(alerts) if alerts else "None"

    fmt_rules = _CHANNEL_FORMAT_RULES[channel].replace("[Customer first name]", first_name)

    return f"""You are the FlowForge customer success agent. FlowForge is a no-code workflow automation SaaS.

== CUSTOMER CONTEXT ==
Name    : {name}
Contact : {contact}
Channel : {channel.value}
Prior messages in this conversation: {state.message_count}
Sentiment: {state.sentiment_label} (score: {state.sentiment_score:+d})
Topics seen: {', '.join(state.topics) or 'none yet'}

== ALERTS ==
{alert_block}

== CONVERSATION HISTORY ==
{history_block}

== FORMAT RULES ==
{fmt_rules}

== RESPONSE RULES ==
1. Lead directly with the answer or action -- never start with "Great question!" or "I understand your frustration"
2. If you need product documentation to answer accurately, call search_docs first
3. If this needs human attention (refund, legal threat, cancellation, very angry/frustrated, repeated unresolved issue after 2+ attempts), call escalate
4. For escalations: after calling escalate, provide a brief human acknowledgement to the customer
5. Always end your response with: How else can I help?
6. Be concise and specific -- no vague placeholders like "contact our team" without a reason""".strip()


# ==============================================================================
# 7. CLAUDE TOOLS  (NEW in v3)
# ==============================================================================

_TOOLS = [
    {
        "name": "search_docs",
        "description": (
            "Search the FlowForge product knowledge base. Use this to look up "
            "troubleshooting steps, feature limits, billing policies, integration setup, "
            "or any product-specific information. Be specific in your query."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Specific search query, e.g. '401 HubSpot OAuth token refresh' not just 'error'"
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "escalate",
        "description": (
            "Route this conversation to a human agent. "
            "tier_1 (immediate, no AI response): legal threats, security incidents, HIPAA, chargeback threats. "
            "tier_2 (AI responds + human follows up): refunds, cancellations, pricing negotiation, "
            "angry/frustrated customer, unresolved issue after multiple attempts. "
            "tier_3 (log silently, no urgency): feature requests, partnership inquiries."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tier": {
                    "type": "string",
                    "enum": ["tier_1", "tier_2", "tier_3"],
                },
                "reason": {
                    "type": "string",
                    "description": "One sentence reason for escalation",
                },
                "route_to": {
                    "type": "string",
                    "description": "legal@flowforge.io | billing@flowforge.io | security@flowforge.io | sales@flowforge.io | human_queue | product_team",
                },
            },
            "required": ["tier", "reason", "route_to"],
        },
    },
]


def _execute_tool(
    tool_name:      str,
    tool_input:     dict,
    kb:             list[DocSection],
    escalation_ctx: dict,
) -> str:
    """Execute a Claude tool call and return the result string."""
    if tool_name == "search_docs":
        query   = tool_input.get("query", "")
        qwords  = extract_query_words(query)
        results = search_docs(qwords, kb, top_k=3)
        if not results:
            return "No matching documentation found for this query. Try different keywords."
        parts = []
        for r in results:
            parts.append(f"## {r.title} (score: {r.score})\n{r.content[:600].strip()}")
        return "\n\n---\n\n".join(parts)

    if tool_name == "escalate":
        tier     = tool_input.get("tier", "tier_2")
        reason   = tool_input.get("reason", "")
        route_to = tool_input.get("route_to", "human_queue")
        escalation_ctx.update(is_escalated=True, tier=tier, reason=reason, route_to=route_to)
        return (
            f"Escalation logged. Tier: {tier} | Route: {route_to} | Reason: {reason}\n"
            "Now write a brief, empathetic acknowledgement for the customer."
        )

    return f"[tool_error] Unknown tool: {tool_name}"


# ==============================================================================
# 8. CLAUDE AGENT LOOP  (NEW in v3)
# ==============================================================================

def run_claude_agent(
    normalized:  str,
    state:       ConversationState,
    channel:     Channel,
    kb:          list[DocSection],
) -> tuple[str, dict, list[AgentTurn]]:
    """
    Run the Claude agentic loop (synchronous).

    Returns:
        (response_text, escalation_ctx, agent_turns)

    escalation_ctx keys: is_escalated, tier, reason, route_to
    """
    import anthropic  # imported here so mock mode works without the package

    client     = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    system     = build_system_prompt(state, channel)
    messages   = [{"role": "user", "content": normalized}]
    esc_ctx    = {"is_escalated": False, "tier": None, "reason": None, "route_to": None}
    turns:     list[AgentTurn] = []
    final_text = ""

    for turn_num in range(1, MAX_AGENT_TURNS + 1):
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=system,
            tools=_TOOLS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            final_text = next(
                (b.text for b in response.content if hasattr(b, "text")), ""
            )
            turns.append(AgentTurn(turn_num=turn_num, action="end_turn", text=final_text))
            break

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = _execute_tool(block.name, block.input, kb, esc_ctx)
                    turns.append(AgentTurn(
                        turn_num=turn_num,
                        action="tool_use",
                        tool_name=block.name,
                        tool_input=dict(block.input),
                        tool_result=result[:300],
                    ))
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "user", "content": tool_results})

    if not final_text:
        # Fallback if max turns hit without end_turn
        final_text = (
            "I'm looking into your request. Our team will follow up shortly. "
            "How else can I help?"
        )
        turns.append(AgentTurn(turn_num=MAX_AGENT_TURNS, action="end_turn", text=final_text))

    return final_text, esc_ctx, turns


# ==============================================================================
# 9. V2 RULE-BASED FALLBACK  (used in mock mode)
# ==============================================================================

_ESCALATION_TEMPLATES = {
    EscalationTier.TIER1: (
        "I've flagged your message as a priority and routed it to the right team. "
        "A specialist will be in touch with you shortly. "
        "Your case has been logged and we'll follow up directly."
    ),
    EscalationTier.TIER2: (
        "I've noted your message and flagged it for follow-up by our team "
        "to make sure everything is fully resolved for you. "
        "In the meantime, here's what I can share:"
    ),
}


def _first_n_lines(text: str, n: int = 6) -> str:
    return "\n".join(l for l in text.splitlines() if l.strip())[:n * 120]


def _extract_snippet(content: str) -> str:
    lines = content.splitlines()
    useful = [l for l in lines if l.strip() and (l.strip()[0].isdigit() or l.strip().startswith("-") or l.strip().startswith("**"))]
    return "\n".join(useful[:8]) if useful else "\n".join(l for l in lines[:6] if l.strip())


def _make_intro(query: str, section_title: str) -> str:
    q = query.lower()
    intros = [
        (["401","authentication","unauthorized","token","reconnect"], f"That '{section_title}' issue is usually a token that needs refreshing -- here's how to fix it:"),
        (["429","rate limit"], "You're hitting the rate limit -- here's how to handle it:"),
        (["not triggering","automation","workflow","isn't triggering"], f"When workflows stop triggering, check these ({section_title}):"),
        (["connect","integration","hubspot","airtable","slack","stripe","webhook"], f"Here's how to set that up ({section_title}):"),
        (["billing","invoice","charge","payment","plan","upgrade","downgrade"], f"On the billing side ({section_title}):"),
        (["refund","money back"], "On refunds -- here's our policy:"),
        (["team","invite","member","role","permission"], f"Here's how team management works ({section_title}):"),
    ]
    for kws, phrase in intros:
        if any(k in q for k in kws):
            return phrase
    return f"Based on your question ({section_title}):"


def _build_context_prefix(state: ConversationState, current_topics: list[str]) -> str:
    if state.message_count == 0:
        return ""
    if state.resolution_status == ResolutionStatus.SOLVED:
        return f"I see this issue has come up again -- let me look into this further."
    overlap = [t for t in current_topics if t in state.topics]
    if overlap:
        return f"I can see you're still experiencing trouble with {overlap[0].replace('_',' ')}. Let me dig deeper."
    return "Thanks for getting back to us."


def generate_response_fallback(
    normalized: str,
    state: ConversationState,
    matched: list[DocSection],
    escalation: EscalationResult,
    channel: Channel,
    current_topics: list[str],
) -> str:
    """Rule-based response generator from v2. Used in mock mode."""
    parts = []
    if escalation.tier == EscalationTier.TIER1:
        return _ESCALATION_TEMPLATES[EscalationTier.TIER1]
    if escalation.tier == EscalationTier.TIER2:
        parts.append(_ESCALATION_TEMPLATES[EscalationTier.TIER2])
    prefix = _build_context_prefix(state, current_topics)
    if prefix:
        parts.append(prefix)
    if state.sentiment_score <= -2 and state.message_count > 0:
        parts.append("I understand this has been frustrating. Here's the next thing to try:")
    if matched:
        top = matched[0]
        parts.append(_make_intro(normalized, top.title))
        parts.append(_extract_snippet(top.content))
        if len(matched) >= 2 and matched[1].title != top.title:
            parts.append(f"\nAlso relevant -- {matched[1].title}:\n{_first_n_lines(matched[1].content)[:200]}")
    else:
        parts.append("Let me check on that -- feel free to visit docs.flowforge.io for our full knowledge base.")
    parts.append("\nHow else can I help?")
    return "\n\n".join(p.strip() for p in parts if p.strip())


# ==============================================================================
# 10. CHANNEL FORMATTING  (for mock mode; Claude handles its own formatting)
# ==============================================================================

def format_response(body: str, channel: Channel, sender_name: Optional[str]) -> str:
    first_name = (sender_name or "").split()[0] if sender_name else None
    if channel == Channel.EMAIL:
        g = f"Hi {first_name}," if first_name else "Hi there,"
        return f"{g}\n\n{body}\n\nBest,\nFlowForge Support"
    if channel == Channel.WHATSAPP:
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", body)
        text = re.sub(r"#{1,3}\s+", "", text)
        text = re.sub(r"`(.+?)`", r"\1", text)
        text = re.sub(r"\n{2,}", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > WHATSAPP_MAX_CHARS:
            cut = text[:WHATSAPP_MAX_CHARS]
            last = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
            if last > WHATSAPP_MAX_CHARS // 2:
                cut = cut[:last + 1]
            text = cut + " -- reply for more"
        return text
    g = f"Hi {first_name}," if first_name else "Hi there,"
    return f"{g}\n\n{body}"


# ==============================================================================
# 11. PIPELINE ORCHESTRATOR  (v3 - stateful + Claude)
# ==============================================================================

def run_pipeline(msg: InboundMessage, kb: list[DocSection]) -> PipelineResult:
    """
    v3 pipeline:
      1.  Resolve customer identity
      2.  Normalize
      3.  Topics & sentiment
      4.  Pre-search docs  (for context injection + mock mode)
      5.  Rule-based escalation pre-check
      6.  History-based escalation pre-check
      7a. TIER 1 detected -> bypass Claude, use template directly
      7b. USE_CLAUDE=True  -> run Claude agent loop
      7c. USE_CLAUDE=False -> run v2 rule-based fallback (mock mode)
      8.  Merge all escalation signals
      9.  Update state
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1-2. Identity + normalize
    cid = resolve_customer_id(msg.sender_email, msg.sender_phone, msg.sender_name, msg.channel)
    state        = get_state(cid)
    is_returning = state.is_returning
    normalized   = normalize(msg)

    # 3. Topics & sentiment
    current_topics = extract_topics(normalized)
    new_score      = update_sentiment(normalized, state.sentiment_score)
    prev_score     = state.sentiment_score

    # 4. Pre-search
    qwords       = extract_query_words(normalized)
    matched_docs = search_docs(qwords, kb)

    # 5-6. Pre-checks
    rule_esc = check_escalation(normalized)
    hist_esc = check_history_escalation(state, current_topics)

    display_name = msg.sender_name or state.customer_name

    # 7. Response generation
    if rule_esc.tier == EscalationTier.TIER1:
        # Immediate escalation -- no Claude, no doc content
        response    = _ESCALATION_TEMPLATES[EscalationTier.TIER1]
        escalation  = rule_esc
        agent_turns = [AgentTurn(turn_num=1, action="pre_check",
                                 text="TIER 1 detected -- bypassing Claude")]
        mode = "pre_check"

    elif USE_CLAUDE:
        # Live Claude mode
        claude_text, esc_ctx, agent_turns = run_claude_agent(normalized, state, msg.channel, kb)
        response = claude_text

        # Build escalation from Claude's tool call (if any)
        if esc_ctx["is_escalated"]:
            try:
                tier_enum = EscalationTier[esc_ctx["tier"].upper()]
            except KeyError:
                tier_enum = EscalationTier.TIER2
            claude_esc = EscalationResult(
                tier=tier_enum,
                reason=esc_ctx.get("reason", ""),
                route=esc_ctx.get("route_to", "human_queue"),
                source="claude",
            )
        else:
            claude_esc = EscalationResult(tier=EscalationTier.NONE)

        escalation = _merge_escalations(_merge_escalations(rule_esc, hist_esc), claude_esc)
        mode = "live"

    else:
        # Mock mode -- v2 rule-based fallback
        pre_esc   = _merge_escalations(rule_esc, hist_esc)
        body      = generate_response_fallback(normalized, state, matched_docs, pre_esc, msg.channel, current_topics)
        response  = format_response(body, msg.channel, display_name)
        escalation = pre_esc
        agent_turns = [AgentTurn(turn_num=1, action="mock",
                                 text="ANTHROPIC_API_KEY not set -- using v2 rule-based fallback")]
        mode = "mock"

    # 8. Update state
    state.message_count   += 1
    state.sentiment_score  = new_score
    state.topics           = merge_topics(state.topics, current_topics)

    if escalation.tier in (EscalationTier.TIER1, EscalationTier.TIER2):
        state.resolution_status = ResolutionStatus.ESCALATED
        state.escalation_tier   = escalation.tier

    state.history.append(HistoryEntry(
        role="user", body=msg.body.strip(), channel=msg.channel,
        timestamp=now, topics=current_topics,
    ))
    state.history.append(HistoryEntry(
        role="agent", body=response, channel=msg.channel,
        timestamp=now, topics=[],
    ))

    return PipelineResult(
        channel=msg.channel, customer_id=cid, is_returning=is_returning,
        original_body=msg.body, normalized_text=normalized,
        query_words=qwords, matched_sections=matched_docs,
        escalation=escalation, response=response, state_snapshot=state,
        message_topics=current_topics, prev_sentiment_score=prev_score,
        agent_turns=agent_turns, mode=mode,
    )


# ==============================================================================
# 12. PRETTY PRINTER  (v3 -- adds agent loop section)
# ==============================================================================

_W = 72

def _bar(char="="): return char * _W
def _section(title): return f"\n  >> {title}"
def _indent(text, spaces=4): return textwrap.indent(text, " " * spaces)


def print_result(result: PipelineResult, index: int, total: int) -> None:
    state = result.state_snapshot
    ch    = result.channel.value.upper().replace("_", " ")
    name  = state.customer_name or "(unknown)"
    tag   = f"[RETURNING -- msg #{state.message_count}]" if result.is_returning else "[NEW CUSTOMER]"
    contact = ", ".join(state.emails) or ", ".join(state.phones) or "(not provided)"
    channels_str = " -> ".join(c.value for c in state.channels_used)

    print(_bar())
    print(f"  EXAMPLE {index}/{total}  [{ch}]   {name}  {tag}")
    print(_bar("-"))

    # -- Customer profile
    print(_section("CUSTOMER PROFILE"))
    print(_indent(f"ID      : {result.customer_id}"))
    print(_indent(f"Name    : {name}"))
    print(_indent(f"Contact : {contact}"))
    print(_indent(f"Channels: {channels_str}   |   Total messages: {state.message_count}"))

    # -- Conversation history
    prior = state.history[:-2]
    print(_section(f"CONVERSATION HISTORY  ({len(prior)} prior entries)"))
    if not prior:
        print(_indent("(first contact -- no prior history)"))
    else:
        shown = prior[-4:] if len(prior) > 4 else prior
        if len(prior) > 4:
            print(_indent(f"... ({len(prior) - 4} earlier entries omitted) ..."))
        for e in shown:
            tag2    = "user " if e.role == "user" else "agent"
            preview = e.body[:75].replace("\n", " ").strip()
            if len(e.body) > 75:
                preview += "..."
            print(_indent(f"[{tag2}] ({e.channel.value:<8}): \"{preview}\""))

    # -- Sentiment & topics
    delta_str = f"{result.state_snapshot.sentiment_score - result.prev_sentiment_score:+d}"
    print(_section("SENTIMENT & TOPICS"))
    print(_indent(
        f"Sentiment : {state.sentiment_label:<14}  score={state.sentiment_score:+d}  (delta: {delta_str})"
    ))
    print(_indent(f"Topics (this msg) : {', '.join(result.message_topics) or 'none'}"))
    print(_indent(f"Topics (cumul.)   : {', '.join(state.topics) or 'none'}"))

    # -- Resolution status
    icons = {ResolutionStatus.OPEN: "[ ] OPEN", ResolutionStatus.SOLVED: "[v] SOLVED", ResolutionStatus.ESCALATED: "[^] ESCALATED"}
    print(_section("RESOLUTION STATUS"))
    print(_indent(icons[state.resolution_status]))
    if state.escalation_tier:
        print(_indent(f"Tier: {state.escalation_tier.value}"))

    # -- Input
    print(_section("INPUT"))
    preview = result.original_body.strip()[:200]
    print(_indent(f'"{preview}{"..." if len(result.original_body.strip()) > 200 else ""}"'))

    # -- NEW in v3: Agent loop
    mode_label = {
        "live":       f"LIVE  |  Model: {CLAUDE_MODEL}",
        "mock":       "MOCK  --  ANTHROPIC_API_KEY not set  (rule-based fallback)",
        "pre_check":  "PRE_CHECK  --  Tier 1 detected, Claude bypassed",
    }[result.mode]
    print(_section(f"CLAUDE AGENT LOOP  [{mode_label}]"))

    tool_count = sum(1 for t in result.agent_turns if t.action == "tool_use")
    for turn in result.agent_turns:
        if turn.action == "tool_use":
            inp_str = ", ".join(f"{k}={json.dumps(v)[:40]}" for k, v in (turn.tool_input or {}).items())
            print(_indent(f"Turn {turn.turn_num}: TOOL_USE  {turn.tool_name}({inp_str})"))
            if turn.tool_result:
                res_preview = turn.tool_result[:120].replace("\n", " ").strip()
                print(_indent(f"         Result : \"{res_preview}...\"", 6))
        elif turn.action == "end_turn":
            print(_indent(f"Turn {turn.turn_num}: END_TURN  ({tool_count} tool call(s) made)"))
        elif turn.action == "mock":
            print(_indent(f"  {turn.text}"))
        elif turn.action == "pre_check":
            print(_indent(f"  {turn.text}"))

    # -- Escalation
    esc   = result.escalation
    t_lbl = {
        EscalationTier.TIER1: "[!!] TIER 1 -- Immediate (no AI resolution)",
        EscalationTier.TIER2: "[!]  TIER 2 -- Respond + flag for human",
        EscalationTier.TIER3: "[*]  TIER 3 -- Flag for review",
        EscalationTier.NONE:  "[ ]  NONE   -- handled by AI",
    }
    s_lbl = {
        "rule":       "Rule-based    (content of this message)",
        "history":    "History-based (repeat topic)",
        "sentiment":  "Sentiment-based (accumulated frustration)",
        "claude":     "Claude tool   (agent called escalate())",
        "pre_check":  "Pre-check     (Tier 1 hard rule)",
    }
    print(_section("ESCALATION CHECK"))
    if esc.should_escalate:
        print(_indent(f"Escalate? YES  {t_lbl[esc.tier]}"))
        print(_indent(f"Source  : {s_lbl.get(esc.source, esc.source)}"))
        print(_indent(f"Reason  : {esc.reason}"))
        print(_indent(f"Route   : {esc.route}"))
        print(_indent(f"Triggers: {esc.keywords_hit}"))
    else:
        print(_indent(f"Escalate? {t_lbl[EscalationTier.NONE]}"))

    # -- Response
    print(_section(f"GENERATED RESPONSE  [{ch}]"))
    print(_indent("-" * (_W - 6)))
    print(_indent(result.response))
    print(_indent("-" * (_W - 6)))
    print()


# ==============================================================================
# 13. TEST MESSAGES  (same 8 as v2)
# ==============================================================================

TEST_MESSAGES: list[InboundMessage] = [

    # Scenario A: Sarah Chen (Email x2 -> WhatsApp) -- cross-channel, history escalation
    InboundMessage(
        channel=Channel.EMAIL, sender_name="Sarah Chen", sender_email="sarah@acme.com",
        body="""
        Hi FlowForge Support,
        I'm getting a "401 Unauthorized" error on my HubSpot integration.
        The workflow was running fine for 2 weeks and now it just stopped.
        I haven't changed anything. I'm on the Growth plan.
        Best regards, Sarah
        """,
    ),
    InboundMessage(
        channel=Channel.EMAIL, sender_name="Sarah Chen", sender_email="sarah@acme.com",
        body="""
        Hi,
        I tried the steps you suggested but I'm still getting the 401 error on HubSpot.
        I re-authenticated the connection and it still shows the same problem.
        This is really important -- our sales pipeline depends on it.
        Sarah
        """,
    ),
    InboundMessage(
        channel=Channel.WHATSAPP, sender_name="Sarah",
        sender_email="sarah@acme.com", sender_phone="+447700900123",
        body="hey still dealing with that 401 hubspot error. been 3 days now "
             "and really frustrated. nothing is working",
    ),

    # Scenario B: Marco (WhatsApp x2) -- cancellation threat
    InboundMessage(
        channel=Channel.WHATSAPP, sender_name="Marco", sender_phone="+447700900456",
        body="hey my automation isn't triggering at all today, was working yesterday. any idea?",
    ),
    InboundMessage(
        channel=Channel.WHATSAPP, sender_name="Marco", sender_phone="+447700900456",
        body="still not working. checked everything. "
             "if this isn't fixed today I'm going to cancel my account and switch to zapier",
    ),

    # Scenario C: James (Web Form) -- new customer, plan change
    InboundMessage(
        channel=Channel.WEB_FORM, sender_name="James Okafor", sender_email="james@startup.io",
        body="""
        Subject: Downgrade from Business to Growth
        Hi, I need to downgrade my plan from Business to Growth.
        Can you tell me what happens to my workflows and when the change takes effect?
        I currently have 18 active workflows.
        """,
    ),

    # Scenario D: Linda (Email) -- refund request
    InboundMessage(
        channel=Channel.EMAIL, sender_name="Linda Park", sender_email="linda@company.com",
        body="""
        Hello,
        I was charged $199 this month even though I downgraded two weeks ago.
        I want a full refund immediately. This is completely unacceptable.
        I've been waiting 3 days for a reply. Linda
        """,
    ),

    # Scenario E: Unknown (WhatsApp) -- Tier 1 legal threat
    InboundMessage(
        channel=Channel.WHATSAPP, sender_phone="+15551234567",
        body="your platform deleted ALL my workflows and I lost weeks of work. "
             "I am contacting my lawyer and taking legal action if this isn't fixed TODAY.",
    ),
]


# ==============================================================================
# 14. MAIN
# ==============================================================================

def main() -> None:
    print("\n" + _bar())
    print("  FlowForge Customer Success Agent -- Prototype Core Loop v3")
    print("  NEW: Real Claude API + tool use (search_docs / escalate)")
    if USE_CLAUDE:
        print(f"  Mode: LIVE  |  Model: {CLAUDE_MODEL}  |  Max turns: {MAX_AGENT_TURNS}")
    else:
        reason = "anthropic package not installed" if not _ANTHROPIC_PKG else "ANTHROPIC_API_KEY not set"
        print(f"  Mode: MOCK  ({reason})  --  rule-based fallback from v2")
    print(_bar())

    kb = load_knowledge_base()
    print(f"\n  Knowledge base: {len(kb)} sections  |  Messages: {len(TEST_MESSAGES)}  |  Scenarios: 5\n")

    for i, msg in enumerate(TEST_MESSAGES, 1):
        result = run_pipeline(msg, kb)
        print_result(result, i, len(TEST_MESSAGES))

    # Summary
    print(_bar())
    print("  CUSTOMER STORE SUMMARY")
    print(_bar("-"))
    print(f"  {'ID':<10} {'Name':<18} {'Msgs':>4}  {'Sentiment':<18} {'Topics':<32} {'Status'}")
    print("  " + "-" * (_W - 2))
    for cid, s in _CUSTOMER_STORE.items():
        nm   = (s.customer_name or "(unknown)")[:17]
        sent = f"{s.sentiment_label} ({s.sentiment_score:+d})"
        tpcs = ", ".join(s.topics[:3]) + ("..." if len(s.topics) > 3 else "")
        print(f"  {cid:<10} {nm:<18} {s.message_count:>4}  {sent:<18} {tpcs:<32} {s.resolution_status.value}")
    print(_bar())
    print(f"  Done -- {len(TEST_MESSAGES)} messages, {len(_CUSTOMER_STORE)} customers")
    print(_bar() + "\n")


if __name__ == "__main__":
    main()
