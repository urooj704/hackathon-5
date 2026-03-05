"""
FlowForge Customer Success Agent -- Prototype Core Loop v1
=========================================================
Exercise 1.2: No LLM calls. Rule-based. Single file. Runnable immediately.

Pipeline per message:
  1. Normalize   -- clean text, extract sender info
  2. Search docs -- simple keyword scoring against product-docs.md sections
  3. Escalate?   -- keyword rules (Tier 1 / Tier 2 / Tier 3)
  4. Build reply -- template + injected doc snippets
  5. Format      -- channel-specific style (Email / WhatsApp / Web Form)

Run:  python prototype_core_loop_v1.py
"""

import re
import sys
import textwrap
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

# Force UTF-8 output on Windows so emojis / special chars print safely
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ==============================================================================
# 0. CONSTANTS & CONFIG
# ==============================================================================

DOCS_PATH = Path(__file__).parent / "context" / "product-docs.md"
WHATSAPP_MAX_CHARS = 280          # keep it SMS-like for the demo
SEARCH_TOP_K = 3                  # max doc sections to surface per query
SEARCH_MIN_SCORE = 1              # min keyword hits to include a section

# Words too common to help narrow down a section
STOP_WORDS = {
    "i", "my", "me", "we", "you", "your", "it", "is", "am", "are", "was",
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "this", "that", "have", "has", "had", "do", "does", "did",
    "be", "been", "can", "will", "would", "could", "should", "not", "no",
    "hi", "hello", "hey", "dear", "regards", "thanks", "thank", "please",
    "need", "help", "how", "what", "when", "why", "where", "get", "want",
    "just", "also", "if", "so", "about", "our", "us", "from", "im", "its",
}

# ==============================================================================
# 1. DATA STRUCTURES
# ==============================================================================

class Channel(Enum):
    EMAIL     = "email"
    WHATSAPP  = "whatsapp"
    WEB_FORM  = "web_form"


class EscalationTier(Enum):
    NONE   = "none"
    TIER1  = "tier_1"   # Immediate -- no resolution attempt
    TIER2  = "tier_2"   # Respond + flag for human
    TIER3  = "tier_3"   # Flag only, no urgency


@dataclass
class InboundMessage:
    """Raw message as received from a channel."""
    channel: Channel
    body: str
    sender_email: Optional[str] = None
    sender_name:  Optional[str] = None
    sender_phone: Optional[str] = None


@dataclass
class DocSection:
    """One section from the knowledge base."""
    title:   str
    content: str
    score:   int = 0       # keyword hit count for this query


@dataclass
class EscalationResult:
    tier:    EscalationTier
    reason:  str = ""
    route:   str = ""
    keywords_hit: list = field(default_factory=list)

    @property
    def should_escalate(self) -> bool:
        return self.tier != EscalationTier.NONE


@dataclass
class PipelineResult:
    """Everything the pipeline produced for one message."""
    channel:          Channel
    original_body:    str
    normalized_text:  str
    query_words:      list[str]
    matched_sections: list[DocSection]
    escalation:       EscalationResult
    response:         str               # final, channel-formatted response


# ==============================================================================
# 2. KNOWLEDGE BASE LOADER
# ==============================================================================

def load_knowledge_base(path: Path = DOCS_PATH) -> list[DocSection]:
    """
    Parse product-docs.md into sections split on ## / ### headings.
    Returns a flat list of DocSection objects.
    """
    if not path.exists():
        print(f"[WARN] docs not found at {path} -- search will return nothing")
        return []

    raw = path.read_text(encoding="utf-8")
    # Split on markdown headings (## or ###)
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
# 3. STEP 1 -- NORMALIZE
# ==============================================================================

def normalize(msg: InboundMessage) -> str:
    """
    Extract clean searchable text from a raw inbound message.

    - Strip email-style quoted replies (lines starting with ">")
    - Remove excessive whitespace / line breaks
    - Collapse to a single readable string
    (Attachments are ignored entirely in this prototype.)
    """
    text = msg.body

    # Drop quoted reply lines (email threads)
    lines = text.splitlines()
    lines = [l for l in lines if not l.strip().startswith(">")]
    text  = " ".join(lines)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


# ==============================================================================
# 4. STEP 2 -- SEARCH DOCS
# ==============================================================================

def extract_query_words(text: str) -> list[str]:
    """
    Tokenise normalised text, remove stop-words, return unique meaningful words.
    """
    words = re.findall(r"[a-z0-9]+", text.lower())
    return list({w for w in words if w not in STOP_WORDS and len(w) > 2})


def search_docs(query_words: list[str], kb: list[DocSection], top_k: int = SEARCH_TOP_K) -> list[DocSection]:
    """
    Score every KB section using title-weighted keyword matching.

    Scoring:
      +3  if the query word appears in the section TITLE  (specific, likely exact topic)
      +1  if the query word appears only in the section BODY  (general mention)

    Title matches dominate so that e.g. "401 Unauthorized" finds section 8.1
    rather than the long FAQ which mentions many generic words.
    Returns top_k sections with score >= SEARCH_MIN_SCORE, highest score first.
    """
    results = []
    for section in kb:
        title_lc   = section.title.lower()
        content_lc = section.content.lower()
        score = 0
        for w in query_words:
            if w in title_lc:
                score += 3          # word found in heading -- strong signal
            elif w in content_lc:
                score += 1          # word found in body -- weaker signal

        if score >= SEARCH_MIN_SCORE:
            results.append(DocSection(
                title=section.title,
                content=section.content,
                score=score,
            ))

    results.sort(key=lambda s: s.score, reverse=True)
    return results[:top_k]


# ==============================================================================
# 5. STEP 3 -- ESCALATION CHECK
# ==============================================================================

# Each entry: (list_of_trigger_phrases, tier, reason, route_to)
_ESCALATION_RULES: list[tuple[list[str], EscalationTier, str, str]] = [

    # -- Tier 1: Immediate, no AI resolution -----------------------------------

    (["my lawyer", "legal action", "lawsuit", "sue you", "i will sue", "litigation",
      "regulatory authority", "report to ftc", "gdpr complaint", "legal team"],
     EscalationTier.TIER1,
     "Customer indicated legal threat or regulatory complaint",
     "legal@flowforge.io"),

    (["data breach", "data exposure", "compromised", "security incident",
      "unauthorized access", "leaked data", "been hacked", "got hacked", "exploit"],
     EscalationTier.TIER1,
     "Potential security incident reported",
     "security@flowforge.io"),

    (["chargeback", "dispute with my bank", "credit card dispute", "will dispute this charge"],
     EscalationTier.TIER1,
     "Customer threatened chargeback",
     "billing@flowforge.io"),

    (["hipaa", "phi", "protected health information", "patient data",
      "business associate agreement", "baa"],
     EscalationTier.TIER1,
     "HIPAA / healthcare data question -- human response required",
     "legal@flowforge.io"),

    # -- Tier 2: Respond + flag ------------------------------------------------

    (["refund", "money back", "want my money", "reimburse", "reimbursement"],
     EscalationTier.TIER2,
     "Refund request -- billing team must approve or deny",
     "billing@flowforge.io"),

    (["cancel my account", "cancellation", "want to cancel", "switching to zapier",
      "switching to make", "leaving flowforge", "closing my account"],
     EscalationTier.TIER2,
     "Customer is considering cancellation -- retention attempt + flag",
     "human_queue"),

    (["give me a discount", "cheaper plan", "negotiate price", "pricing negotiation",
      "custom pricing", "can you reduce"],
     EscalationTier.TIER2,
     "Discount / pricing negotiation request",
     "sales@flowforge.io"),

    (["this is ridiculous", "this is unacceptable", "absolutely terrible",
      "worst service", "completely useless", "total garbage", "fraud",
      "scam", "rip off", "ripped off"],
     EscalationTier.TIER2,
     "Angry / highly frustrated customer",
     "human_queue"),

    # -- Tier 3: Flag for review, no urgency ----------------------------------

    (["would be great if", "feature request", "please add", "suggestion for",
      "feature idea", "can you add"],
     EscalationTier.TIER3,
     "Feature request -- log for product team",
     "product_team"),

    (["partner with", "reseller", "partnership inquiry", "affiliate program",
      "integrate with us"],
     EscalationTier.TIER3,
     "Partnership / reseller inquiry",
     "partnerships@flowforge.io"),
]

_PROFANITY = {"damn", "hell", "crap", "shit", "fuck", "ass", "bastard", "idiot"}

def check_escalation(text: str) -> EscalationResult:
    """
    Rule-based escalation detector.

    Checks:
      1. Phrase-based rules (ordered Tier1 -> Tier3)
      2. ALL-CAPS heuristic (>=6 consecutive uppercase words -> Tier 2)
      3. Profanity list -> Tier 2
    """
    lower = text.lower()

    for phrases, tier, reason, route in _ESCALATION_RULES:
        hits = [p for p in phrases if p in lower]
        if hits:
            return EscalationResult(tier=tier, reason=reason, route=route, keywords_hit=hits)

    # ALL-CAPS check: ≥3 uppercase words in a row
    words = text.split()
    caps_run = 0
    for w in words:
        if re.fullmatch(r"[A-Z]{3,}[!?]*", w):
            caps_run += 1
            if caps_run >= 3:
                return EscalationResult(
                    tier=EscalationTier.TIER2,
                    reason="Message written in ALL CAPS -- likely angry customer",
                    route="human_queue",
                    keywords_hit=["ALL_CAPS"],
                )
        else:
            caps_run = 0

    # Profanity check
    tokens = set(re.findall(r"[a-z]+", lower))
    found_profanity = tokens & _PROFANITY
    if found_profanity:
        return EscalationResult(
            tier=EscalationTier.TIER2,
            reason="Message contains strong language",
            route="human_queue",
            keywords_hit=list(found_profanity),
        )

    return EscalationResult(tier=EscalationTier.NONE)


# ==============================================================================
# 6. STEP 4 -- BUILD RESPONSE BODY (channel-neutral)
# ==============================================================================

# Escalation acknowledgement templates (channel-neutral body, formatted later)
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
    """Return first n non-empty lines of a doc section."""
    lines = [l for l in text.splitlines() if l.strip()]
    return "\n".join(lines[:n])


def build_response_body(
    normalized: str,
    matched: list[DocSection],
    escalation: EscalationResult,
    channel: Channel,
) -> str:
    """
    Assemble a channel-neutral response body from:
      - escalation templates (if applicable)
      - relevant doc snippets
      - generic fallback

    Channel-specific formatting (greeting, sign-off, length) is applied
    in the next step.
    """

    # -- Tier 1 escalations: template only, no doc content --------------------
    if escalation.tier == EscalationTier.TIER1:
        return _ESCALATION_TEMPLATES[EscalationTier.TIER1]

    parts = []

    # -- Tier 2: prepend flag notice, then continue with helpful content -------
    if escalation.tier == EscalationTier.TIER2:
        parts.append(_ESCALATION_TEMPLATES[EscalationTier.TIER2])

    # -- Build content from matched doc sections -------------------------------
    if matched:
        top = matched[0]    # best-scoring section

        # Introductory line
        intro = _make_intro(normalized, top.title)
        parts.append(intro)

        # Pull the most useful snippet from the top section
        snippet = _extract_snippet(top.content)
        parts.append(snippet)

        # If a second section adds something different, include a brief note
        if len(matched) >= 2 and matched[1].title != top.title:
            second_snippet = _first_n_lines(matched[1].content, 3)
            parts.append(f"\nAlso relevant -- {matched[1].title}:\n{second_snippet}")

    else:
        # Generic fallback when docs have no match
        parts.append(
            "I want to make sure I give you accurate information on this. "
            "Let me check on that and get back to you, or feel free to visit "
            "docs.flowforge.io for our full knowledge base."
        )

    # Closing line (always)
    parts.append("\nHow else can I help?")

    return "\n\n".join(p.strip() for p in parts if p.strip())


def _make_intro(query: str, section_title: str) -> str:
    """Generate a one-line intro sentence that connects the query to the section found."""
    q = query.lower()

    # Pair keywords -> natural intro phrases
    intros = [
        (["401", "authentication", "unauthorized", "token", "reconnect"],
         f"That '{section_title}' issue is usually a token that needs refreshing -- here's how to fix it:"),

        (["429", "rate limit", "too many requests"],
         "You're hitting the rate limit on the target app -- here's how to handle it:"),

        (["413", "payload too large", "too large"],
         "The payload is exceeding the 5 MB limit -- here's the fix:"),

        (["not triggering", "not firing", "not working", "not running", "broken", "stuck"],
         f"When workflows stop triggering, there are a few things to check ({section_title}):"),

        (["connect", "integration", "setup", "airtable", "hubspot", "slack",
          "stripe", "gmail", "google sheets", "webhook"],
         f"Here's how to set that up ({section_title}):"),

        (["billing", "invoice", "charge", "payment", "plan", "upgrade", "downgrade"],
         f"On the billing side ({section_title}):"),

        (["refund", "money back"],
         "On refunds -- here's our policy:"),

        (["limit", "quota", "tasks", "exceeded", "how many"],
         f"Here's the relevant limit information ({section_title}):"),

        (["team", "invite", "member", "role", "permission", "sso"],
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


def _extract_snippet(content: str) -> str:
    """
    Return the most informative part of a doc section.
    Prefers numbered/bullet lists; falls back to first 6 lines.
    """
    lines = content.splitlines()
    # Keep lines that look like steps, bullets, or table rows
    useful = [
        l for l in lines
        if l.strip() and (
            l.strip()[0].isdigit()
            or l.strip().startswith("-")
            or l.strip().startswith("|")
            or l.strip().startswith("**")
            or l.strip().startswith("•")
        )
    ]
    if useful:
        return "\n".join(useful[:8])
    return _first_n_lines(content, 6)


# ==============================================================================
# 7. STEP 5 -- CHANNEL FORMATTING
# ==============================================================================

def format_response(body: str, channel: Channel, sender_name: Optional[str]) -> str:
    """
    Wrap the channel-neutral response body in the correct channel style.

    EMAIL    : formal greeting + structured body + "Best, FlowForge Support"
    WHATSAPP : strip markdown, truncate to WHATSAPP_MAX_CHARS, casual
    WEB_FORM : "Hi [Name]," + medium length + light sign-off
    """
    first_name = (sender_name or "").split()[0] if sender_name else None

    if channel == Channel.EMAIL:
        return _format_email(body, first_name)
    elif channel == Channel.WHATSAPP:
        return _format_whatsapp(body)
    else:  # WEB_FORM
        return _format_web_form(body, first_name)


def _format_email(body: str, first_name: Optional[str]) -> str:
    greeting = f"Hi {first_name}," if first_name else "Hi there,"
    sign_off  = "Best,\nFlowForge Support"
    return f"{greeting}\n\n{body}\n\n{sign_off}"


def _format_whatsapp(body: str) -> str:
    # Strip markdown bold/italic and headers
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", body)   # **bold** -> bold
    text = re.sub(r"#{1,3}\s+", "", text)            # ## heading -> heading
    text = re.sub(r"`(.+?)`", r"\1", text)           # `code` -> code
    text = re.sub(r"\n{2,}", " ", text)              # multi-newlines -> space
    text = re.sub(r"\s+", " ", text).strip()

    # Truncate to WHATSAPP_MAX_CHARS, breaking cleanly on a sentence
    if len(text) > WHATSAPP_MAX_CHARS:
        cut = text[:WHATSAPP_MAX_CHARS]
        # Try to break at last sentence ending
        last_stop = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
        if last_stop > WHATSAPP_MAX_CHARS // 2:
            cut = cut[: last_stop + 1]
        text = cut + " -- reply for more (ok)"

    return text


def _format_web_form(body: str, first_name: Optional[str]) -> str:
    greeting = f"Hi {first_name}," if first_name else "Hi there,"
    return f"{greeting}\n\n{body}"


# ==============================================================================
# 8. PIPELINE ORCHESTRATOR
# ==============================================================================

def run_pipeline(msg: InboundMessage, kb: list[DocSection]) -> PipelineResult:
    """Run all 5 steps for one inbound message and return a PipelineResult."""

    # Step 1 -- Normalize
    normalized = normalize(msg)

    # Step 2 -- Search
    query_words  = extract_query_words(normalized)
    matched_docs = search_docs(query_words, kb)

    # Step 3 -- Escalation check
    escalation = check_escalation(normalized)

    # Step 4 -- Build response body (channel-neutral)
    body = build_response_body(normalized, matched_docs, escalation, msg.channel)

    # Step 5 -- Channel formatting
    response = format_response(body, msg.channel, msg.sender_name)

    return PipelineResult(
        channel=msg.channel,
        original_body=msg.body,
        normalized_text=normalized,
        query_words=query_words,
        matched_sections=matched_docs,
        escalation=escalation,
        response=response,
    )


# ==============================================================================
# 9. PRETTY PRINTER
# ==============================================================================

_W = 72  # output width

def _bar(char="=") -> str:
    return char * _W

def _section(title: str) -> str:
    return f"\n  >> {title}"

def _indent(text: str, spaces: int = 4) -> str:
    return textwrap.indent(text, " " * spaces)

def print_result(result: PipelineResult, index: int) -> None:
    ch = result.channel.value.upper().replace("_", " ")

    print(_bar())
    print(f"  EXAMPLE {index}  [{ch}]")
    print(_bar("-"))

    # -- Input ----------------------------------------------------------------
    print(_section("INPUT"))
    print(_indent(f'"{result.original_body.strip()}"'))

    # -- Normalized -----------------------------------------------------------
    print(_section("NORMALIZED TEXT"))
    norm_preview = result.normalized_text[:200] + ("..." if len(result.normalized_text) > 200 else "")
    print(_indent(f'"{norm_preview}"'))

    # -- Doc search -----------------------------------------------------------
    print(_section("DOCS SEARCHED"))
    print(_indent(f"Query words: {result.query_words}"))
    if result.matched_sections:
        print(_indent(f"Matched {len(result.matched_sections)} section(s):"))
        for i, sec in enumerate(result.matched_sections, 1):
            preview = sec.content[:120].replace("\n", " ") + "..."
            print(_indent(f"[{i}] {sec.title}  (score: {sec.score})", 6))
            print(_indent(f'    "{preview}"', 6))
    else:
        print(_indent("No sections matched above threshold."))

    # -- Escalation -----------------------------------------------------------
    print(_section("ESCALATION CHECK"))
    esc = result.escalation
    if esc.should_escalate:
        tier_label = {
            EscalationTier.TIER1: "[!!] TIER 1 -- Immediate escalation (no AI resolution)",
            EscalationTier.TIER2: "[!]  TIER 2 -- Respond + flag for human follow-up",
            EscalationTier.TIER3: "[*]  TIER 3 -- Flag for review, no urgency",
        }[esc.tier]
        print(_indent(f"Escalate? YES -- {tier_label}"))
        print(_indent(f"Reason   : {esc.reason}"))
        print(_indent(f"Route to : {esc.route}"))
        print(_indent(f"Triggers : {esc.keywords_hit}"))
    else:
        print(_indent("Escalate? NO -- handle with AI response"))

    # -- Response -------------------------------------------------------------
    print(_section(f"GENERATED RESPONSE  [{result.channel.value.upper()}]"))
    print(_indent("-" * (_W - 6)))
    print(_indent(result.response))
    print(_indent("-" * (_W - 6)))
    print()


# ==============================================================================
# 10. HARDCODED TEST MESSAGES
# ==============================================================================

TEST_MESSAGES: list[InboundMessage] = [

    # -- Example 1: EMAIL -- integration auth error -----------------------------
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

    # -- Example 2: WHATSAPP -- quick trigger question --------------------------
    InboundMessage(
        channel=Channel.WHATSAPP,
        sender_name="Marco",
        sender_phone="+447700900123",
        body="hey my automation isn't triggering at all today, was working yesterday. any idea? 😅",
    ),

    # -- Example 3: WEB FORM -- billing / plan change question -----------------
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

    # -- Example 4: EMAIL -- refund request (Tier 2 escalation) ----------------
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

    # -- Example 5: WHATSAPP -- legal threat (Tier 1 immediate escalation) -----
    InboundMessage(
        channel=Channel.WHATSAPP,
        sender_phone="+15551234567",
        body="your platform deleted ALL my workflows and I lost weeks of work. "
             "I am contacting my lawyer and taking legal action if this isn't fixed TODAY.",
    ),

]


# ==============================================================================
# 11. MAIN
# ==============================================================================

def main() -> None:
    print("\n" + _bar())
    print("  FlowForge Customer Success Agent -- Prototype Core Loop v1")
    print(_bar())

    # Load knowledge base once
    kb = load_knowledge_base()
    print(f"\n  Knowledge base loaded: {len(kb)} sections from product-docs.md\n")

    # Run pipeline for each test message
    for i, msg in enumerate(TEST_MESSAGES, 1):
        result = run_pipeline(msg, kb)
        print_result(result, i)

    print(_bar())
    print(f"  Done -- {len(TEST_MESSAGES)} messages processed")
    print(_bar() + "\n")


if __name__ == "__main__":
    main()
