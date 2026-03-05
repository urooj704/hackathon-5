"""
FlowForge Customer Success Agent -- Prototype Core Loop v2
==========================================================
Exercise 1.3: Add memory & state on top of v1 pipeline.

NEW in v2:
  - In-memory customer store  (dict of customer_id -> ConversationState)
  - Identity resolution       (email + phone -> single customer record)
  - Conversation history      (cross-channel, per customer)
  - Sentiment tracking        (rule-based keyword scoring, cumulative)
  - Topic detection           (keyword-based tagging)
  - Resolution status         (open / solved / escalated)
  - History-aware responses   (acknowledge follow-ups, repeat-issue detection)
  - History-based escalation  (sentiment score OR repeat topic -> Tier 2)

New functions:
  resolve_customer_id()          -- unified identity (email + phone)
  update_sentiment()             -- cumulative keyword-based scoring
  extract_topics()               -- keyword-based topic tagging
  generate_response_with_context()  -- history-aware response body
  check_history_escalation()     -- escalate based on conversation patterns

Run:  python prototype_core_loop_v2.py
"""

from __future__ import annotations

import re
import sys
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

# Force UTF-8 output on Windows so special chars print safely
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ==============================================================================
# 0. CONSTANTS & CONFIG
# ==============================================================================

DOCS_PATH           = Path(__file__).parent / "context" / "product-docs.md"
WHATSAPP_MAX_CHARS  = 280
SEARCH_TOP_K        = 3
SEARCH_MIN_SCORE    = 1

# History-based escalation thresholds
SENTIMENT_ESCALATE_SCORE     = -3   # cumulative score <= -3  -> Tier 2
REPEAT_ISSUE_MSG_THRESHOLD   = 2    # >=2 prior msgs same topic -> Tier 2

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
    """Raw message as received from a channel."""
    channel:      Channel
    body:         str
    sender_email: Optional[str] = None
    sender_name:  Optional[str] = None
    sender_phone: Optional[str] = None


@dataclass
class DocSection:
    """One section from the knowledge base."""
    title:   str
    content: str
    score:   int = 0


@dataclass
class EscalationResult:
    tier:         EscalationTier
    reason:       str  = ""
    route:        str  = ""
    keywords_hit: list = field(default_factory=list)
    source:       str  = "rule"   # "rule" | "history" | "sentiment"

    @property
    def should_escalate(self) -> bool:
        return self.tier != EscalationTier.NONE


@dataclass
class HistoryEntry:
    """One turn in a customer conversation."""
    role:      str            # "user" | "agent"
    body:      str
    channel:   Channel
    timestamp: str            # ISO-like string
    topics:    list = field(default_factory=list)


@dataclass
class ConversationState:
    """Per-customer in-memory state, tracked across all messages."""
    customer_id:       str
    customer_name:     Optional[str]
    emails:            set            # all email addresses seen
    phones:            set            # all phone numbers seen
    history:           list           # list[HistoryEntry]
    sentiment_score:   int            # cumulative, clamped to [-5, +5]
    topics:            list           # unique topic tags, cumulative
    resolution_status: ResolutionStatus
    original_channel:  Channel
    channels_used:     list           # list[Channel], in order first seen
    escalation_tier:   Optional[EscalationTier]
    message_count:     int            # user messages only

    @property
    def sentiment_label(self) -> str:
        if self.sentiment_score >= 2:
            return "positive"
        elif self.sentiment_score >= -1:
            return "neutral"
        elif self.sentiment_score >= -3:
            return "negative"
        else:
            return "very_negative"

    @property
    def is_returning(self) -> bool:
        """True if customer has sent at least one previous message."""
        return self.message_count >= 1


@dataclass
class PipelineResult:
    """Everything the v2 pipeline produced for one message."""
    channel:              Channel
    customer_id:          str
    is_returning:         bool
    original_body:        str
    normalized_text:      str
    query_words:          list
    matched_sections:     list
    escalation:           EscalationResult
    response:             str
    state_snapshot:       ConversationState   # state AFTER this message
    message_topics:       list                # topics from THIS message only
    prev_sentiment_score: int                 # sentiment BEFORE this message


# ==============================================================================
# 2. IN-MEMORY CUSTOMER STORE
# ==============================================================================

_CUSTOMER_STORE: dict[str, ConversationState] = {}
_EMAIL_INDEX:    dict[str, str] = {}    # email (lower) -> customer_id
_PHONE_INDEX:    dict[str, str] = {}    # phone -> customer_id
_ID_COUNTER:     list[int]      = [0]   # mutable counter (list trick for closure)


def _next_customer_id() -> str:
    _ID_COUNTER[0] += 1
    return f"CUST-{_ID_COUNTER[0]:04d}"


def resolve_customer_id(
    email:   Optional[str],
    phone:   Optional[str],
    name:    Optional[str],
    channel: Channel,
) -> str:
    """
    Return existing customer_id or create a new one.

    Lookup order:
      1. email index (primary)
      2. phone index (secondary)
      3. Create new customer

    If both email AND phone resolve to different existing records,
    email takes precedence.
    """
    cid = None

    if email and email.lower() in _EMAIL_INDEX:
        cid = _EMAIL_INDEX[email.lower()]

    if cid is None and phone and phone in _PHONE_INDEX:
        cid = _PHONE_INDEX[phone]

    if cid is None:
        cid = _next_customer_id()
        _CUSTOMER_STORE[cid] = ConversationState(
            customer_id=cid,
            customer_name=name,
            emails=set(),
            phones=set(),
            history=[],
            sentiment_score=0,
            topics=[],
            resolution_status=ResolutionStatus.OPEN,
            original_channel=channel,
            channels_used=[],
            escalation_tier=None,
            message_count=0,
        )

    state = _CUSTOMER_STORE[cid]

    # Enrich existing record with any new identifiers / name
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


def get_state(customer_id: str) -> ConversationState:
    return _CUSTOMER_STORE[customer_id]


# ==============================================================================
# 3. SENTIMENT TRACKING
# ==============================================================================

_POSITIVE_WORDS = {
    "thanks", "thank", "great", "excellent", "perfect", "love", "wonderful",
    "awesome", "helpful", "resolved", "fixed", "working", "brilliant", "solved",
    "appreciate", "amazing", "fantastic", "happy",
}

_NEGATIVE_WORDS = {
    "broken", "error", "issue", "problem", "failed", "failing", "frustrated",
    "angry", "disappointed", "wrong", "terrible", "awful", "ridiculous",
    "unacceptable", "horrible", "joke", "useless", "garbage",
}

_VERY_NEGATIVE_WORDS = {
    "unacceptable", "fraud", "scam", "garbage", "useless", "worst",
    "rip off", "ripped off", "absolutely terrible", "total garbage",
}

_STILL_BROKEN_PHRASES = [
    "still not working", "still broken", "still failing",
    "didn't fix", "not fixed", "same issue", "same error", "same problem",
    "still having trouble", "still having the same",
]


def update_sentiment(text: str, current_score: int) -> int:
    """
    Adjust cumulative sentiment score based on new message text.
    Returns new score clamped to [-5, +5].

    Scoring per message:
      +1  per positive word
      -1  per negative word
      -1  extra per very-negative word (stacks)
      -2  if a "still broken" persistence phrase is found (once)
    """
    lower = text.lower()
    delta = 0

    for w in _POSITIVE_WORDS:
        if w in lower:
            delta += 1

    for w in _NEGATIVE_WORDS:
        if w in lower:
            delta -= 1

    for w in _VERY_NEGATIVE_WORDS:
        if w in lower:
            delta -= 1      # extra on top of _NEGATIVE_WORDS

    for phrase in _STILL_BROKEN_PHRASES:
        if phrase in lower:
            delta -= 2
            break           # count persistence penalty once

    return max(-5, min(5, current_score + delta))


# ==============================================================================
# 4. TOPIC DETECTION
# ==============================================================================

_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "authentication":   ["401", "unauthorized", "token", "reconnect", "oauth",
                         "credentials", "login", "403", "auth"],
    "billing":          ["invoice", "charge", "payment", "billing", "charged",
                         "subscription", "cost", "price", "199", "99"],
    "plan_change":      ["upgrade", "downgrade", "plan", "business plan",
                         "growth plan", "starter", "tier"],
    "workflow_trigger": ["trigger", "triggering", "not firing", "automation",
                         "workflow", "not running", "isn't triggering"],
    "integration":      ["hubspot", "airtable", "slack", "stripe", "gmail",
                         "integration", "connect", "webhook"],
    "rate_limit":       ["429", "rate limit", "too many requests", "throttle"],
    "legal":            ["lawyer", "legal", "sue", "lawsuit", "litigation"],
    "data_loss":        ["deleted", "lost", "missing", "disappeared", "gone"],
    "performance":      ["slow", "timeout", "delay", "hanging", "stuck"],
    "team_management":  ["team", "invite", "member", "role", "permission", "sso"],
    "refund":           ["refund", "money back", "reimburse", "reimbursement"],
    "cancellation":     ["cancel", "cancellation", "leaving", "switching to",
                         "closing my account"],
}


def extract_topics(text: str) -> list[str]:
    """Return topic tags detected in text using keyword matching."""
    lower = text.lower()
    return [t for t, kws in _TOPIC_KEYWORDS.items() if any(kw in lower for kw in kws)]


def merge_topics(existing: list[str], new_topics: list[str]) -> list[str]:
    """Add new topics to existing list, preserving order, no duplicates."""
    result = list(existing)
    for t in new_topics:
        if t not in result:
            result.append(t)
    return result


# ==============================================================================
# 5. KNOWLEDGE BASE LOADER  (unchanged from v1)
# ==============================================================================

def load_knowledge_base(path: Path = DOCS_PATH) -> list[DocSection]:
    if not path.exists():
        print(f"[WARN] docs not found at {path} -- search will return nothing")
        return []

    raw = path.read_text(encoding="utf-8")
    pattern = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)
    matches = list(pattern.finditer(raw))

    sections = []
    for i, m in enumerate(matches):
        title = m.group(2).strip()
        start = m.end()
        end   = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        body  = raw[start:end].strip()
        if body:
            sections.append(DocSection(title=title, content=body))

    return sections


# ==============================================================================
# 6. NORMALIZE  (unchanged from v1)
# ==============================================================================

def normalize(msg: InboundMessage) -> str:
    text  = msg.body
    lines = [l for l in text.splitlines() if not l.strip().startswith(">")]
    text  = " ".join(lines)
    return re.sub(r"\s+", " ", text).strip()


# ==============================================================================
# 7. SEARCH DOCS  (unchanged from v1)
# ==============================================================================

def extract_query_words(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return list({w for w in words if w not in STOP_WORDS and len(w) > 2})


def search_docs(
    query_words: list[str],
    kb:          list[DocSection],
    top_k:       int = SEARCH_TOP_K,
) -> list[DocSection]:
    """
    Title-weighted keyword scoring:
      +3  word found in section title  (strong signal)
      +1  word found in section body   (weaker signal)
    """
    results = []
    for section in kb:
        title_lc   = section.title.lower()
        content_lc = section.content.lower()
        score = 0
        for w in query_words:
            if w in title_lc:
                score += 3
            elif w in content_lc:
                score += 1
        if score >= SEARCH_MIN_SCORE:
            results.append(DocSection(
                title=section.title,
                content=section.content,
                score=score,
            ))

    results.sort(key=lambda s: s.score, reverse=True)
    return results[:top_k]


# ==============================================================================
# 8. ESCALATION CHECK
# ==============================================================================

_ESCALATION_RULES: list[tuple[list[str], EscalationTier, str, str]] = [

    # -- Tier 1 ----------------------------------------------------------------
    (["my lawyer", "legal action", "lawsuit", "sue you", "i will sue",
      "litigation", "regulatory authority", "report to ftc", "gdpr complaint"],
     EscalationTier.TIER1,
     "Customer indicated legal threat or regulatory complaint",
     "legal@flowforge.io"),

    (["data breach", "data exposure", "compromised", "security incident",
      "unauthorized access", "leaked data", "been hacked", "got hacked", "exploit"],
     EscalationTier.TIER1,
     "Potential security incident reported",
     "security@flowforge.io"),

    (["chargeback", "dispute with my bank", "credit card dispute",
      "will dispute this charge"],
     EscalationTier.TIER1,
     "Customer threatened chargeback",
     "billing@flowforge.io"),

    (["hipaa", "phi", "protected health information", "patient data",
      "business associate agreement", "baa"],
     EscalationTier.TIER1,
     "HIPAA / healthcare data question -- human response required",
     "legal@flowforge.io"),

    # -- Tier 2 ----------------------------------------------------------------
    (["refund", "money back", "want my money", "reimburse", "reimbursement"],
     EscalationTier.TIER2,
     "Refund request -- billing team must approve or deny",
     "billing@flowforge.io"),

    (["cancel my account", "cancellation", "want to cancel",
      "switching to zapier", "switch to zapier", "switching to make",
      "leaving flowforge", "closing my account"],
     EscalationTier.TIER2,
     "Customer is considering cancellation -- retention attempt + flag",
     "human_queue"),

    (["give me a discount", "cheaper plan", "negotiate price",
      "pricing negotiation", "custom pricing", "can you reduce"],
     EscalationTier.TIER2,
     "Discount / pricing negotiation request",
     "sales@flowforge.io"),

    (["this is ridiculous", "this is unacceptable", "absolutely terrible",
      "worst service", "completely useless", "total garbage", "fraud",
      "scam", "rip off", "ripped off"],
     EscalationTier.TIER2,
     "Angry / highly frustrated customer",
     "human_queue"),

    # -- Tier 3 ----------------------------------------------------------------
    (["would be great if", "feature request", "please add",
      "suggestion for", "feature idea", "can you add"],
     EscalationTier.TIER3,
     "Feature request -- log for product team",
     "product_team"),

    (["partner with", "reseller", "partnership inquiry",
      "affiliate program", "integrate with us"],
     EscalationTier.TIER3,
     "Partnership / reseller inquiry",
     "partnerships@flowforge.io"),
]

_PROFANITY = {"damn", "hell", "crap", "shit", "fuck", "ass", "bastard", "idiot"}


def check_escalation(text: str) -> EscalationResult:
    """Rule-based escalation: phrase matching, ALL-CAPS, profanity."""
    lower = text.lower()

    for phrases, tier, reason, route in _ESCALATION_RULES:
        hits = [p for p in phrases if p in lower]
        if hits:
            return EscalationResult(
                tier=tier, reason=reason, route=route,
                keywords_hit=hits, source="rule",
            )

    # ALL-CAPS check (3+ consecutive uppercase words)
    caps_run = 0
    for w in text.split():
        if re.fullmatch(r"[A-Z]{3,}[!?]*", w):
            caps_run += 1
            if caps_run >= 3:
                return EscalationResult(
                    tier=EscalationTier.TIER2,
                    reason="Message written in ALL CAPS -- likely angry customer",
                    route="human_queue",
                    keywords_hit=["ALL_CAPS"],
                    source="rule",
                )
        else:
            caps_run = 0

    # Profanity check
    found_profanity = set(re.findall(r"[a-z]+", lower)) & _PROFANITY
    if found_profanity:
        return EscalationResult(
            tier=EscalationTier.TIER2,
            reason="Message contains strong language",
            route="human_queue",
            keywords_hit=list(found_profanity),
            source="rule",
        )

    return EscalationResult(tier=EscalationTier.NONE)


def check_history_escalation(
    state:          ConversationState,
    current_topics: list[str],
) -> Optional[EscalationResult]:
    """
    Escalate based on conversation HISTORY patterns:

    1. Cumulative sentiment <= SENTIMENT_ESCALATE_SCORE (-3)
       -> Tier 2 (customer very frustrated, needs human empathy)

    2. >= REPEAT_ISSUE_MSG_THRESHOLD prior messages about the same topic
       -> Tier 2 (persistent issue, AI alone is not resolving it)
    """
    # Check 1: accumulated frustration
    if state.sentiment_score <= SENTIMENT_ESCALATE_SCORE:
        return EscalationResult(
            tier=EscalationTier.TIER2,
            reason=(
                f"Customer sentiment very negative "
                f"(score: {state.sentiment_score}) -- needs human empathy"
            ),
            route="human_queue",
            keywords_hit=[f"sentiment_score={state.sentiment_score}"],
            source="sentiment",
        )

    # Check 2: repeat topic after multiple messages
    if state.message_count >= REPEAT_ISSUE_MSG_THRESHOLD:
        overlap = [t for t in current_topics if t in state.topics]
        if overlap:
            return EscalationResult(
                tier=EscalationTier.TIER2,
                reason=(
                    f"Persistent issue after {state.message_count} messages "
                    f"on: {', '.join(overlap)} -- AI not resolving, needs human"
                ),
                route="human_queue",
                keywords_hit=[f"repeat:{t}" for t in overlap],
                source="history",
            )

    return None


def _merge_escalations(
    rule_esc:    EscalationResult,
    history_esc: Optional[EscalationResult],
) -> EscalationResult:
    """Return the higher-priority escalation (Tier 1 > Tier 2 > Tier 3 > None)."""
    if history_esc is None:
        return rule_esc

    priority = {
        EscalationTier.TIER1: 3,
        EscalationTier.TIER2: 2,
        EscalationTier.TIER3: 1,
        EscalationTier.NONE:  0,
    }
    return history_esc if priority[history_esc.tier] > priority[rule_esc.tier] else rule_esc


# ==============================================================================
# 9. CONTEXT-AWARE RESPONSE GENERATION
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


def _build_context_prefix(
    state:          ConversationState,
    current_topics: list[str],
) -> str:
    """
    Returns a context-aware opening sentence for returning customers.
    Returns empty string for first-time contacts.
    """
    if state.message_count == 0:
        return ""   # first message, no history

    # Re-opened after being marked solved
    if state.resolution_status == ResolutionStatus.SOLVED:
        topic_str = current_topics[0].replace("_", " ") if current_topics else "this"
        return (
            f"I see your {topic_str} issue has come up again -- "
            "let me look into this further for you."
        )

    # Persistent issue: same topics as before
    overlap = [t for t in current_topics if t in state.topics]
    if overlap:
        topic_label = overlap[0].replace("_", " ")
        return (
            f"I can see you're still experiencing trouble with {topic_label}. "
            "Let me dig deeper into this."
        )

    # General follow-up, different topic
    return "Thanks for getting back to us."


def _first_n_lines(text: str, n: int = 6) -> str:
    lines = [l for l in text.splitlines() if l.strip()]
    return "\n".join(lines[:n])


def _extract_snippet(content: str) -> str:
    lines = content.splitlines()
    useful = [
        l for l in lines
        if l.strip() and (
            l.strip()[0].isdigit()
            or l.strip().startswith("-")
            or l.strip().startswith("|")
            or l.strip().startswith("**")
        )
    ]
    if useful:
        return "\n".join(useful[:8])
    return _first_n_lines(content, 6)


def _make_intro(query: str, section_title: str) -> str:
    q = query.lower()
    intros = [
        (["401", "authentication", "unauthorized", "token", "reconnect"],
         f"That '{section_title}' issue is usually a token that needs refreshing -- here's how to fix it:"),
        (["429", "rate limit", "too many requests"],
         "You're hitting the rate limit on the target app -- here's how to handle it:"),
        (["413", "payload too large"],
         "The payload is exceeding the 5 MB limit -- here's the fix:"),
        (["not triggering", "not firing", "automation", "workflow", "isn't triggering"],
         f"When workflows stop triggering, there are a few things to check ({section_title}):"),
        (["connect", "integration", "hubspot", "airtable", "slack", "stripe", "webhook"],
         f"Here's how to set that up ({section_title}):"),
        (["billing", "invoice", "charge", "payment", "plan", "upgrade", "downgrade"],
         f"On the billing side ({section_title}):"),
        (["refund", "money back"],
         "On refunds -- here's our policy:"),
        (["limit", "quota", "tasks", "exceeded"],
         f"Here's the relevant limit information ({section_title}):"),
        (["team", "invite", "member", "role", "permission"],
         f"Here's how team management works ({section_title}):"),
        (["trial", "free", "expire"],
         "On the trial:"),
        (["history", "log", "execution", "failed run"],
         f"To find your execution history ({section_title}):"),
    ]
    for keywords, phrase in intros:
        if any(kw in q for kw in keywords):
            return phrase
    return f"Based on your question, here's the most relevant information ({section_title}):"


def generate_response_with_context(
    normalized:     str,
    state:          ConversationState,
    matched:        list[DocSection],
    escalation:     EscalationResult,
    channel:        Channel,
    current_topics: list[str],
) -> str:
    """
    Build a channel-neutral response body using history context.

    Adds over v1:
      - Context-aware opening for returning customers
      - Empathy line when cumulative sentiment is negative
    """
    parts = []

    # Tier 1: template only, no doc content
    if escalation.tier == EscalationTier.TIER1:
        return _ESCALATION_TEMPLATES[EscalationTier.TIER1]

    # Tier 2: flag notice first, then continue
    if escalation.tier == EscalationTier.TIER2:
        parts.append(_ESCALATION_TEMPLATES[EscalationTier.TIER2])

    # Context-aware opening for returning customers
    context_prefix = _build_context_prefix(state, current_topics)
    if context_prefix:
        parts.append(context_prefix)

    # Empathy line for recurring frustration
    if state.sentiment_score <= -2 and state.message_count > 0:
        parts.append(
            "I understand this has been frustrating. "
            "Here's the next thing to try:"
        )

    # Doc content
    if matched:
        top = matched[0]
        parts.append(_make_intro(normalized, top.title))
        parts.append(_extract_snippet(top.content))

        if len(matched) >= 2 and matched[1].title != top.title:
            second = _first_n_lines(matched[1].content, 3)
            parts.append(f"\nAlso relevant -- {matched[1].title}:\n{second}")
    else:
        parts.append(
            "I want to make sure I give you accurate information on this. "
            "Let me check on that and get back to you, or feel free to visit "
            "docs.flowforge.io for our full knowledge base."
        )

    parts.append("\nHow else can I help?")
    return "\n\n".join(p.strip() for p in parts if p.strip())


# ==============================================================================
# 10. CHANNEL FORMATTING  (unchanged from v1)
# ==============================================================================

def format_response(body: str, channel: Channel, sender_name: Optional[str]) -> str:
    first_name = (sender_name or "").split()[0] if sender_name else None
    if channel == Channel.EMAIL:
        return _format_email(body, first_name)
    elif channel == Channel.WHATSAPP:
        return _format_whatsapp(body)
    else:
        return _format_web_form(body, first_name)


def _format_email(body: str, first_name: Optional[str]) -> str:
    greeting = f"Hi {first_name}," if first_name else "Hi there,"
    return f"{greeting}\n\n{body}\n\nBest,\nFlowForge Support"


def _format_whatsapp(body: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", body)
    text = re.sub(r"#{1,3}\s+", "", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"\n{2,}", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) > WHATSAPP_MAX_CHARS:
        cut = text[:WHATSAPP_MAX_CHARS]
        last_stop = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
        if last_stop > WHATSAPP_MAX_CHARS // 2:
            cut = cut[:last_stop + 1]
        text = cut + " -- reply for more"

    return text


def _format_web_form(body: str, first_name: Optional[str]) -> str:
    greeting = f"Hi {first_name}," if first_name else "Hi there,"
    return f"{greeting}\n\n{body}"


# ==============================================================================
# 11. PIPELINE ORCHESTRATOR  (v2 - stateful)
# ==============================================================================

def run_pipeline(msg: InboundMessage, kb: list[DocSection]) -> PipelineResult:
    """
    Run the full v2 pipeline for one inbound message.

    Steps:
      1.  Resolve customer identity    -> create or retrieve ConversationState
      2.  Normalize message text
      3.  Extract topics & compute new sentiment score
      4.  Search knowledge base
      5.  Rule-based escalation check  (content of THIS message)
      6.  History-based escalation     (patterns across ALL messages)
      7.  Merge escalations            (higher tier wins)
      8.  Generate context-aware response body
      9.  Apply channel formatting
      10. Persist to state             (history, topics, sentiment, status)
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Identity
    cid = resolve_customer_id(
        email=msg.sender_email,
        phone=msg.sender_phone,
        name=msg.sender_name,
        channel=msg.channel,
    )
    state        = get_state(cid)
    is_returning = state.is_returning

    # 2. Normalize
    normalized = normalize(msg)

    # 3. Topics & sentiment
    current_topics    = extract_topics(normalized)
    new_score         = update_sentiment(normalized, state.sentiment_score)
    prev_score        = state.sentiment_score

    # 4. Search
    query_words  = extract_query_words(normalized)
    matched_docs = search_docs(query_words, kb)

    # 5. Rule-based escalation
    rule_esc = check_escalation(normalized)

    # 6. History-based escalation (uses pre-update state scores)
    hist_esc = check_history_escalation(state, current_topics)

    # 7. Merge
    escalation = _merge_escalations(rule_esc, hist_esc)

    # 8. Build response body
    display_name = msg.sender_name or state.customer_name
    body = generate_response_with_context(
        normalized, state, matched_docs, escalation, msg.channel, current_topics,
    )

    # 9. Format for channel
    response = format_response(body, msg.channel, display_name)

    # 10. Update state
    state.message_count   += 1
    state.sentiment_score  = new_score
    state.topics           = merge_topics(state.topics, current_topics)

    if escalation.tier in (EscalationTier.TIER1, EscalationTier.TIER2):
        state.resolution_status = ResolutionStatus.ESCALATED
        state.escalation_tier   = escalation.tier

    state.history.append(HistoryEntry(
        role="user", body=msg.body.strip(),
        channel=msg.channel, timestamp=now, topics=current_topics,
    ))
    state.history.append(HistoryEntry(
        role="agent", body=response,
        channel=msg.channel, timestamp=now, topics=[],
    ))

    return PipelineResult(
        channel=msg.channel,
        customer_id=cid,
        is_returning=is_returning,
        original_body=msg.body,
        normalized_text=normalized,
        query_words=query_words,
        matched_sections=matched_docs,
        escalation=escalation,
        response=response,
        state_snapshot=state,
        message_topics=current_topics,
        prev_sentiment_score=prev_score,
    )


# ==============================================================================
# 12. PRETTY PRINTER  (v2 - extended output)
# ==============================================================================

_W = 72


def _bar(char: str = "=") -> str:
    return char * _W


def _section(title: str) -> str:
    return f"\n  >> {title}"


def _indent(text: str, spaces: int = 4) -> str:
    return textwrap.indent(text, " " * spaces)


def print_result(result: PipelineResult, index: int, total: int) -> None:
    state  = result.state_snapshot
    ch     = result.channel.value.upper().replace("_", " ")
    name   = state.customer_name or "(unknown)"

    if result.is_returning:
        customer_tag = f"[RETURNING -- message #{state.message_count}]"
    else:
        customer_tag = "[NEW CUSTOMER]"

    contact = ", ".join(state.emails) or ", ".join(state.phones) or "(not provided)"
    channels_str = " -> ".join(c.value for c in state.channels_used)

    # -- Header ---------------------------------------------------------------
    print(_bar())
    print(f"  EXAMPLE {index}/{total}  [{ch}]   {name}  {customer_tag}")
    print(_bar("-"))

    # -- Customer profile -----------------------------------------------------
    print(_section("CUSTOMER PROFILE"))
    print(_indent(f"ID       : {result.customer_id}"))
    print(_indent(f"Name     : {name}"))
    print(_indent(f"Contact  : {contact}"))
    print(_indent(f"Channels : {channels_str}"))
    print(_indent(f"Total messages so far : {state.message_count}"))

    # -- Conversation history (prior turns only) -------------------------------
    prior = state.history[:-2]   # everything before the current user+agent pair
    print(_section(f"CONVERSATION HISTORY  ({len(prior)} prior entries)"))
    if not prior:
        print(_indent("(first contact -- no prior history)"))
    else:
        shown = prior[-4:] if len(prior) > 4 else prior
        if len(prior) > 4:
            print(_indent(f"... ({len(prior) - 4} earlier entries omitted) ..."))
        for entry in shown:
            role_tag = "user " if entry.role == "user" else "agent"
            preview  = entry.body[:75].replace("\n", " ").strip()
            if len(entry.body) > 75:
                preview += "..."
            print(_indent(f"[{role_tag}] ({entry.channel.value:<8}): \"{preview}\""))

    # -- Sentiment & topics ---------------------------------------------------
    score_delta = result.state_snapshot.sentiment_score - result.prev_sentiment_score
    delta_str   = f"{score_delta:+d}" if score_delta != 0 else "0"

    print(_section("SENTIMENT & TOPICS"))
    print(_indent(
        f"Sentiment : {state.sentiment_label:<14} "
        f"score={state.sentiment_score:+d}  "
        f"(delta from this message: {delta_str})"
    ))
    print(_indent(f"Topics (this msg) : {', '.join(result.message_topics) or 'none'}"))
    print(_indent(f"Topics (cumul.)   : {', '.join(state.topics) or 'none'}"))

    # -- Resolution status ----------------------------------------------------
    status_icons = {
        ResolutionStatus.OPEN:      "[ ] OPEN",
        ResolutionStatus.SOLVED:    "[v] SOLVED",
        ResolutionStatus.ESCALATED: "[^] ESCALATED",
    }
    print(_section("RESOLUTION STATUS"))
    print(_indent(status_icons[state.resolution_status]))
    if state.escalation_tier:
        print(_indent(f"Escalation tier : {state.escalation_tier.value}"))

    # -- Input ----------------------------------------------------------------
    print(_section("INPUT"))
    body_preview = result.original_body.strip()[:200]
    suffix = "..." if len(result.original_body.strip()) > 200 else ""
    print(_indent(f'"{body_preview}{suffix}"'))

    # -- Doc search -----------------------------------------------------------
    print(_section("DOCS SEARCHED"))
    print(_indent(f"Query words : {result.query_words}"))
    if result.matched_sections:
        print(_indent(f"Matched {len(result.matched_sections)} section(s):"))
        for i, sec in enumerate(result.matched_sections, 1):
            preview = sec.content[:90].replace("\n", " ").strip() + "..."
            print(_indent(f"[{i}] {sec.title}  (score: {sec.score})", 6))
            print(_indent(f'    "{preview}"', 6))
    else:
        print(_indent("No sections matched above threshold."))

    # -- Escalation -----------------------------------------------------------
    esc = result.escalation
    tier_labels = {
        EscalationTier.TIER1: "[!!] TIER 1 -- Immediate escalation (no AI resolution)",
        EscalationTier.TIER2: "[!]  TIER 2 -- Respond + flag for human follow-up",
        EscalationTier.TIER3: "[*]  TIER 3 -- Flag for review, no urgency",
        EscalationTier.NONE:  "[ ]  NONE   -- handle with AI response",
    }
    source_labels = {
        "rule":      "Rule-based   (content of this message)",
        "history":   "History-based (repeat topic across messages)",
        "sentiment": "Sentiment-based (accumulated frustration score)",
    }

    print(_section("ESCALATION CHECK"))
    if esc.should_escalate:
        print(_indent(f"Escalate? YES  {tier_labels[esc.tier]}"))
        print(_indent(f"Source   : {source_labels.get(esc.source, esc.source)}"))
        print(_indent(f"Reason   : {esc.reason}"))
        print(_indent(f"Route to : {esc.route}"))
        print(_indent(f"Triggers : {esc.keywords_hit}"))
    else:
        print(_indent(f"Escalate? {tier_labels[EscalationTier.NONE]}"))

    # -- Response -------------------------------------------------------------
    print(_section(f"GENERATED RESPONSE  [{ch}]"))
    print(_indent("-" * (_W - 6)))
    print(_indent(result.response))
    print(_indent("-" * (_W - 6)))
    print()


# ==============================================================================
# 13. TEST MESSAGES  (8 messages across 5 customers)
# ==============================================================================

TEST_MESSAGES: list[InboundMessage] = [

    # =========================================================================
    # Scenario A: Sarah Chen  (Email -> Email -> WhatsApp)
    # Shows: cross-channel tracking, history-aware prefix, history-based
    #        escalation firing on 3rd message (sentiment score -3 + repeat topic)
    # =========================================================================

    # A-1: First contact via Email -- 401 error on HubSpot
    InboundMessage(
        channel=Channel.EMAIL,
        sender_name="Sarah Chen",
        sender_email="sarah@acme.com",
        body="""
        Hi FlowForge Support,

        I'm getting a "401 Unauthorized" error on my HubSpot integration.
        The workflow was running fine for 2 weeks and now it just stopped.
        I haven't changed anything on my end.

        Can you help me fix this? I'm on the Growth plan.

        Best regards,
        Sarah
        """,
    ),

    # A-2: Follow-up Email -- tried the fix, still broken (returning customer)
    InboundMessage(
        channel=Channel.EMAIL,
        sender_name="Sarah Chen",
        sender_email="sarah@acme.com",
        body="""
        Hi,

        I tried the steps you suggested but I'm still getting the 401 error on HubSpot.
        I re-authenticated the connection and it still shows the same problem.

        This is really important for my business -- our sales pipeline depends on it.

        Sarah
        """,
    ),

    # A-3: WhatsApp -- 3rd message, still unresolved, frustrated
    #      NOTE: email is passed so the system recognises her across channels.
    #      In production this would come from account lookup by phone number.
    InboundMessage(
        channel=Channel.WHATSAPP,
        sender_name="Sarah",
        sender_email="sarah@acme.com",     # linked from account registration
        sender_phone="+447700900123",
        body="hey still dealing with that 401 hubspot error. been 3 days now "
             "and really frustrated. nothing is working",
    ),

    # =========================================================================
    # Scenario B: Marco  (WhatsApp x2)
    # Shows: rule-based escalation (cancellation threat) on 2nd message
    # =========================================================================

    # B-1: First contact -- automation not triggering
    InboundMessage(
        channel=Channel.WHATSAPP,
        sender_name="Marco",
        sender_phone="+447700900456",
        body="hey my automation isn't triggering at all today, was working yesterday. any idea?",
    ),

    # B-2: Follow-up -- still broken, cancellation threat
    InboundMessage(
        channel=Channel.WHATSAPP,
        sender_name="Marco",
        sender_phone="+447700900456",
        body="still not working. checked everything. "
             "if this isn't fixed today I'm going to cancel my account and switch to zapier",
    ),

    # =========================================================================
    # Scenario C: James Okafor  (Web Form)
    # Shows: new customer, neutral plan change inquiry, clean handling
    # =========================================================================

    InboundMessage(
        channel=Channel.WEB_FORM,
        sender_name="James Okafor",
        sender_email="james@startup.io",
        body="""
        Subject: Downgrade from Business to Growth

        Hi, I need to downgrade my plan from Business to Growth.
        Can you tell me what happens to my workflows and when the change takes effect?
        I currently have 18 active workflows.
        """,
    ),

    # =========================================================================
    # Scenario D: Linda Park  (Email)
    # Shows: Tier 2 rule-based escalation (refund request + frustration)
    # =========================================================================

    InboundMessage(
        channel=Channel.EMAIL,
        sender_name="Linda Park",
        sender_email="linda@company.com",
        body="""
        Hello,

        I was charged $199 this month even though I downgraded my account two weeks ago.
        I want a full refund for this charge immediately.

        This is completely unacceptable. I've been waiting for 3 days for a reply.

        Linda
        """,
    ),

    # =========================================================================
    # Scenario E: Unknown caller  (WhatsApp)
    # Shows: Tier 1 rule-based escalation (legal threat, immediate routing)
    # =========================================================================

    InboundMessage(
        channel=Channel.WHATSAPP,
        sender_phone="+15551234567",
        body="your platform deleted ALL my workflows and I lost weeks of work. "
             "I am contacting my lawyer and taking legal action if this isn't fixed TODAY.",
    ),
]


# ==============================================================================
# 14. MAIN
# ==============================================================================

def main() -> None:
    print("\n" + _bar())
    print("  FlowForge Customer Success Agent -- Prototype Core Loop v2")
    print("  NEW: in-memory state, identity resolution, sentiment, topics,")
    print("       history-based escalation")
    print(_bar())

    kb = load_knowledge_base()
    print(f"\n  Knowledge base loaded: {len(kb)} sections from product-docs.md")
    print(f"  Processing {len(TEST_MESSAGES)} test messages across 5 customer scenarios\n")

    for i, msg in enumerate(TEST_MESSAGES, 1):
        result = run_pipeline(msg, kb)
        print_result(result, i, len(TEST_MESSAGES))

    # -- Summary table --------------------------------------------------------
    print(_bar())
    print("  CUSTOMER STORE SUMMARY")
    print(_bar("-"))
    print(f"  {'ID':<10} {'Name':<18} {'Msgs':>4}  {'Sentiment':<14} {'Topics':<35} {'Status'}")
    print("  " + "-" * (_W - 2))
    for cid, state in _CUSTOMER_STORE.items():
        name      = (state.customer_name or "(unknown)")[:17]
        sentiment = f"{state.sentiment_label} ({state.sentiment_score:+d})"
        topics    = ", ".join(state.topics[:3]) + ("..." if len(state.topics) > 3 else "")
        status    = state.resolution_status.value
        print(f"  {cid:<10} {name:<18} {state.message_count:>4}  {sentiment:<14} {topics:<35} {status}")
    print(_bar())
    print(f"  Done -- {len(TEST_MESSAGES)} messages, {len(_CUSTOMER_STORE)} unique customers")
    print(_bar() + "\n")


if __name__ == "__main__":
    main()
