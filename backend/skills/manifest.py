"""
Agent Skills Manifest — FlowForge Customer Success FTE

Skills are reusable, composable capabilities that the agent invokes.
Each skill has:
  - When to use it
  - Required inputs
  - Expected outputs
  - Fallback behavior

Skills are invoked by the agent core and can wrap tool calls,
LLM inference, or rule-based logic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ─── Channel enum (shared across skills) ─────────────────────────────────────

class Channel(str, Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"


# ─── Sentiment labels ─────────────────────────────────────────────────────────

class SentimentLabel(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    CONFUSED = "confused"
    FRUSTRATED = "frustrated"
    ANXIOUS = "anxious"
    ANGRY = "angry"
    FURIOUS = "furious"


# ─── Skill result types ───────────────────────────────────────────────────────

@dataclass
class KnowledgeResult:
    """Output of the Knowledge Retrieval Skill."""
    found: bool
    results: list[dict[str, Any]]
    query_used: str
    top_similarity: float = 0.0


@dataclass
class SentimentResult:
    """Output of the Sentiment Analysis Skill."""
    score: float           # -5.0 to +5.0
    label: SentimentLabel
    confidence: float      # 0.0 to 1.0
    keywords: list[str] = field(default_factory=list)


@dataclass
class EscalationResult:
    """Output of the Escalation Decision Skill."""
    should_escalate: bool
    tier: Optional[str]    # "tier_1", "tier_2", "tier_3" or None
    reason: Optional[str]
    route_to: Optional[str]
    trigger_type: str      # "keyword" | "sentiment" | "history" | "none"


@dataclass
class ChannelResponse:
    """Output of the Channel Adaptation Skill."""
    formatted_text: str
    channel: Channel
    truncated: bool = False
    char_count: int = 0


@dataclass
class CustomerIdentity:
    """Output of the Customer Identification Skill."""
    customer_id: Optional[str]
    is_new_customer: bool
    email: Optional[str]
    phone: Optional[str]
    previous_channels: list[str] = field(default_factory=list)
    ticket_count: int = 0


# ─── Skill 1: Knowledge Retrieval ─────────────────────────────────────────────

class KnowledgeRetrievalSkill:
    """
    Semantic search over the FlowForge product knowledge base.

    When to use:
        Customer asks any product/technical question.

    Inputs:
        query (str): Raw customer query text
        max_results (int): Maximum results to return (default: 5)

    Outputs:
        KnowledgeResult with found docs and similarity scores

    Fallback:
        If similarity < threshold or DB unavailable, returns found=False
    """

    name = "knowledge_retrieval"
    description = "Search product documentation for relevant information"
    similarity_threshold = 0.70
    default_max_results = 5

    async def execute(
        self,
        query: str,
        max_results: int = 5,
        db_session: Any = None,
    ) -> KnowledgeResult:
        """
        Execute knowledge search.

        In production: generates embedding via OpenAI, searches pgvector.
        In prototype: uses keyword matching as fallback.
        """
        if db_session is not None:
            return await self._search_with_db(query, max_results, db_session)

        # Fallback: keyword-based mock for testing
        return self._mock_search(query)

    async def _search_with_db(self, query: str, max_results: int, db_session: Any) -> KnowledgeResult:
        """Real pgvector search (requires OpenAI + PostgreSQL)."""
        try:
            import openai, os
            client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            embed_resp = await client.embeddings.create(
                model="text-embedding-3-small",
                input=query,
            )
            embedding = embed_resp.data[0].embedding

            from sqlalchemy import text
            result = await db_session.execute(
                text("""
                    SELECT section_title, content,
                           1 - (embedding <=> :emb::vector) AS similarity
                    FROM doc_chunks
                    ORDER BY embedding <=> :emb::vector
                    LIMIT :limit
                """),
                {"emb": str(embedding), "limit": max_results},
            )
            rows = result.fetchall()

            results = [
                {
                    "title": row.section_title or "Documentation",
                    "content": row.content,
                    "similarity": float(row.similarity),
                }
                for row in rows
                if float(row.similarity) >= self.similarity_threshold
            ]

            return KnowledgeResult(
                found=len(results) > 0,
                results=results,
                query_used=query,
                top_similarity=results[0]["similarity"] if results else 0.0,
            )
        except Exception as e:
            return KnowledgeResult(found=False, results=[], query_used=query)

    def _mock_search(self, query: str) -> KnowledgeResult:
        """Keyword-based fallback for development without DB."""
        keywords = query.lower().split()
        mock_doc = {
            "title": "FlowForge Documentation",
            "content": f"Relevant information for: {query}. "
                       "FlowForge supports automated workflows with 100+ integrations.",
            "similarity": 0.80,
        }
        return KnowledgeResult(
            found=True,
            results=[mock_doc],
            query_used=query,
            top_similarity=0.80,
        )


# ─── Skill 2: Sentiment Analysis ──────────────────────────────────────────────

class SentimentAnalysisSkill:
    """
    Analyze customer message sentiment and assign a score.

    When to use:
        Every inbound customer message, before generating response.

    Inputs:
        message (str): Raw customer message text

    Outputs:
        SentimentResult with score (-5 to +5), label, confidence

    Escalation thresholds:
        score <= -5: Tier 1 (furious — no AI response)
        score <= -3: Tier 2 (angry/frustrated — AI response + human flag)
    """

    name = "sentiment_analysis"
    description = "Analyze customer sentiment to guide response tone and escalation"

    # Negative keywords with weights
    NEGATIVE_KEYWORDS: dict[str, float] = {
        "furious": -5, "outraged": -5, "lawsuit": -5, "lawyer": -5,
        "sue": -4.5, "chargeback": -4.5, "fraud": -4.5,
        "terrible": -3.5, "horrible": -3.5, "unacceptable": -3.5, "disgusting": -3.5,
        "angry": -3, "frustrated": -2.5, "ridiculous": -2.5, "useless": -2.5,
        "disappointed": -2, "unhappy": -2, "annoyed": -2,
        "not working": -1.5, "broken": -1.5, "failed": -1.5,
        "confused": -1, "issue": -0.5, "problem": -0.5,
    }

    # Positive keywords with weights
    POSITIVE_KEYWORDS: dict[str, float] = {
        "amazing": 4, "excellent": 4, "outstanding": 4, "love": 3.5,
        "great": 3, "fantastic": 3, "brilliant": 3,
        "good": 2, "helpful": 2, "wonderful": 2,
        "thanks": 1.5, "thank you": 1.5, "appreciate": 1.5,
        "okay": 0.5, "fine": 0.5, "works": 0.5,
    }

    def execute(self, message: str) -> SentimentResult:
        """Rule-based sentiment analysis with keyword scoring."""
        text = message.lower()
        score = 0.0
        triggered_keywords = []

        for keyword, weight in self.NEGATIVE_KEYWORDS.items():
            if keyword in text:
                score += weight
                triggered_keywords.append(keyword)

        for keyword, weight in self.POSITIVE_KEYWORDS.items():
            if keyword in text:
                score += weight

        # Exclamation marks add intensity
        exclamations = text.count("!")
        if score < 0:
            score -= min(exclamations * 0.5, 2.0)
        elif score > 0:
            score += min(exclamations * 0.3, 1.0)

        # Clamp to [-5, +5]
        score = max(-5.0, min(5.0, score))

        # Map to label
        if score <= -4.5:
            label = SentimentLabel.FURIOUS
        elif score <= -3.0:
            label = SentimentLabel.ANGRY
        elif score <= -1.5:
            label = SentimentLabel.FRUSTRATED
        elif score <= -0.5:
            label = SentimentLabel.ANXIOUS
        elif score <= 0.5:
            label = SentimentLabel.NEUTRAL
        elif score <= 1.5:
            label = SentimentLabel.CONFUSED
        else:
            label = SentimentLabel.POSITIVE

        confidence = 0.85 if triggered_keywords else 0.60

        return SentimentResult(
            score=round(score, 2),
            label=label,
            confidence=confidence,
            keywords=triggered_keywords,
        )


# ─── Skill 3: Escalation Decision ─────────────────────────────────────────────

class EscalationDecisionSkill:
    """
    Decide whether to escalate a ticket to human agents.

    When to use:
        After generating agent response, before sending.

    Inputs:
        message (str): Customer message
        sentiment (SentimentResult): Current sentiment
        history (list): Previous messages in conversation
        ticket_topic (str): Current topic

    Outputs:
        EscalationResult with should_escalate, tier, reason, route_to
    """

    name = "escalation_decision"
    description = "Decide if and how to escalate to human support"

    TIER_1_KEYWORDS = [
        "chargeback", "dispute", "credit card dispute", "fraud",
        "lawyer", "legal action", "sue", "lawsuit",
        "gdpr delete", "data deletion", "right to erasure",
        "security breach", "hacked", "unauthorized access",
        "press", "journalist", "media",
    ]

    TIER_2_KEYWORDS = [
        "refund", "money back", "cancel", "cancellation",
        "data loss", "lost my data", "corrupted",
        "outage", "completely broken", "not working at all",
    ]

    TIER_3_KEYWORDS = [
        "feature request", "would love to see", "suggest",
        "partnership", "integrate with", "investor",
        "enterprise plan", "custom pricing",
    ]

    ROUTE_MAP = {
        "billing": "billing@flowforge.io",
        "legal": "legal@flowforge.io",
        "security": "security@flowforge.io",
        "engineering": "engineering_oncall",
        "general": "human_queue",
        "sales": "sales@flowforge.io",
        "partnerships": "partnerships@flowforge.io",
    }

    def execute(
        self,
        message: str,
        sentiment: SentimentResult,
        history: list[dict] = None,
        ticket_topic: str = "",
    ) -> EscalationResult:
        text = message.lower()
        history = history or []

        # Tier 1 checks (immediate escalation)
        for keyword in self.TIER_1_KEYWORDS:
            if keyword in text:
                route = self._determine_route(keyword)
                return EscalationResult(
                    should_escalate=True,
                    tier="tier_1",
                    reason=f"Keyword trigger: '{keyword}' detected",
                    route_to=route,
                    trigger_type="keyword",
                )

        # Sentiment-based Tier 1
        if sentiment.score <= -5.0:
            return EscalationResult(
                should_escalate=True,
                tier="tier_1",
                reason=f"Sentiment score {sentiment.score} (furious)",
                route_to=self.ROUTE_MAP["general"],
                trigger_type="sentiment",
            )

        # Tier 2 checks
        for keyword in self.TIER_2_KEYWORDS:
            if keyword in text:
                route = self._determine_route(keyword)
                return EscalationResult(
                    should_escalate=True,
                    tier="tier_2",
                    reason=f"Tier 2 keyword: '{keyword}'",
                    route_to=route,
                    trigger_type="keyword",
                )

        # Sentiment-based Tier 2
        if sentiment.score <= -3.0:
            return EscalationResult(
                should_escalate=True,
                tier="tier_2",
                reason=f"Sustained negative sentiment (score: {sentiment.score})",
                route_to=self.ROUTE_MAP["general"],
                trigger_type="sentiment",
            )

        # History-based escalation: same topic repeated 3+ times
        if ticket_topic and history:
            topic_count = sum(
                1 for msg in history
                if ticket_topic.lower() in msg.get("body", "").lower()
            )
            if topic_count >= 2:
                return EscalationResult(
                    should_escalate=True,
                    tier="tier_2",
                    reason=f"Topic '{ticket_topic}' repeated {topic_count + 1} times",
                    route_to=self.ROUTE_MAP["general"],
                    trigger_type="history",
                )

        # Tier 3 checks
        for keyword in self.TIER_3_KEYWORDS:
            if keyword in text:
                route = self._determine_route(keyword)
                return EscalationResult(
                    should_escalate=True,
                    tier="tier_3",
                    reason=f"Tier 3 signal: '{keyword}'",
                    route_to=route,
                    trigger_type="keyword",
                )

        return EscalationResult(
            should_escalate=False,
            tier=None,
            reason=None,
            route_to=None,
            trigger_type="none",
        )

    def _determine_route(self, keyword: str) -> str:
        billing_words = {"refund", "chargeback", "dispute", "billing", "invoice", "cancel"}
        legal_words = {"lawyer", "legal", "sue", "lawsuit", "gdpr", "erasure"}
        security_words = {"breach", "hacked", "unauthorized", "security"}
        sales_words = {"enterprise", "pricing", "custom", "investor"}
        partner_words = {"partnership", "integrate", "collaboration"}

        kw = keyword.lower()
        if any(w in kw for w in billing_words):
            return self.ROUTE_MAP["billing"]
        if any(w in kw for w in legal_words):
            return self.ROUTE_MAP["legal"]
        if any(w in kw for w in security_words):
            return self.ROUTE_MAP["security"]
        if any(w in kw for w in sales_words):
            return self.ROUTE_MAP["sales"]
        if any(w in kw for w in partner_words):
            return self.ROUTE_MAP["partnerships"]
        return self.ROUTE_MAP["general"]


# ─── Skill 4: Channel Adaptation ──────────────────────────────────────────────

class ChannelAdaptationSkill:
    """
    Format agent response appropriately for the target channel.

    When to use:
        Before every outbound message.

    Inputs:
        response_text (str): Raw response from the agent
        channel (Channel): Target channel
        ticket_id (str): Ticket reference ID
        customer_name (str): Optional customer name for personalization

    Outputs:
        ChannelResponse with formatted text
    """

    name = "channel_adaptation"
    description = "Format response appropriately for the target communication channel"

    WHATSAPP_MAX = 1600
    EMAIL_SIGNATURE = (
        "\n\nBest regards,\nFlowForge AI Support Team\n"
        "---\nThis response was generated by our AI assistant. "
        "For complex issues, a human agent will follow up."
    )

    def execute(
        self,
        response_text: str,
        channel: Channel,
        ticket_id: str = "",
        customer_name: str = "Customer",
    ) -> ChannelResponse:
        if channel == Channel.EMAIL:
            return self._format_email(response_text, ticket_id, customer_name)
        elif channel == Channel.WHATSAPP:
            return self._format_whatsapp(response_text, ticket_id)
        else:
            return self._format_web_form(response_text, ticket_id)

    def _format_email(self, text: str, ticket_id: str, name: str) -> ChannelResponse:
        formatted = (
            f"Dear {name},\n\n"
            f"Thank you for reaching out to FlowForge Support.\n\n"
            f"{text}"
            f"{self.EMAIL_SIGNATURE}"
        )
        if ticket_id:
            formatted += f"\nTicket Reference: {ticket_id}"
        return ChannelResponse(
            formatted_text=formatted,
            channel=Channel.EMAIL,
            truncated=False,
            char_count=len(formatted),
        )

    def _format_whatsapp(self, text: str, ticket_id: str) -> ChannelResponse:
        # Remove markdown (WhatsApp uses its own bold/italic)
        clean = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
        clean = re.sub(r'#{1,6}\s+', '', clean)
        clean = re.sub(r'`(.+?)`', r'\1', clean)

        suffix = f"\n\n📱 Reply for more help or type *human* for live support."
        if ticket_id:
            suffix += f"\nRef: {ticket_id}"

        max_body = self.WHATSAPP_MAX - len(suffix)
        truncated = False

        if len(clean) > max_body:
            clean = clean[:max_body - 3] + "..."
            truncated = True

        formatted = clean + suffix
        return ChannelResponse(
            formatted_text=formatted,
            channel=Channel.WHATSAPP,
            truncated=truncated,
            char_count=len(formatted),
        )

    def _format_web_form(self, text: str, ticket_id: str) -> ChannelResponse:
        formatted = text
        suffix = "\n\n---\n"
        if ticket_id:
            suffix += f"Your ticket ID: **{ticket_id}**\n"
        suffix += "Need more help? Reply to this email or visit [support.flowforge.io](https://support.flowforge.io)"
        formatted += suffix
        return ChannelResponse(
            formatted_text=formatted,
            channel=Channel.WEB_FORM,
            truncated=False,
            char_count=len(formatted),
        )


# ─── Skill 5: Customer Identification ─────────────────────────────────────────

class CustomerIdentificationSkill:
    """
    Resolve customer identity from message metadata across all channels.

    When to use:
        On every inbound message, before anything else.

    Inputs:
        email (str | None): Customer email address
        phone (str | None): Customer phone number (E.164)
        name (str | None): Customer display name

    Outputs:
        CustomerIdentity with unified customer_id and history summary

    Resolution chain:
        1. Look up by email (primary key)
        2. Look up by phone (secondary)
        3. Create new customer record

    Cross-channel linking:
        If a WhatsApp phone matches an email from a previous web form ticket,
        they are linked to the same customer record.
    """

    name = "customer_identification"
    description = "Resolve unified customer identity across all channels"

    async def execute(
        self,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        name: Optional[str] = None,
        db_session: Any = None,
    ) -> CustomerIdentity:
        if db_session is None:
            return self._mock_resolve(email, phone, name)

        return await self._resolve_with_db(email, phone, name, db_session)

    async def _resolve_with_db(
        self,
        email: Optional[str],
        phone: Optional[str],
        name: Optional[str],
        db_session: Any,
    ) -> CustomerIdentity:
        from sqlalchemy import text

        customer = None

        # 1. Try email lookup
        if email:
            result = await db_session.execute(
                text("SELECT id, email, phone FROM customers WHERE email = :email"),
                {"email": email},
            )
            customer = result.fetchone()

        # 2. Try phone lookup
        if not customer and phone:
            result = await db_session.execute(
                text("SELECT id, email, phone FROM customers WHERE phone = :phone"),
                {"phone": phone},
            )
            customer = result.fetchone()

        # 3. Create new customer
        if not customer:
            result = await db_session.execute(
                text(
                    "INSERT INTO customers (email, phone, name) VALUES (:email, :phone, :name) RETURNING id"
                ),
                {"email": email, "phone": phone, "name": name or ""},
            )
            customer_id = str(result.scalar())
            await db_session.commit()
            return CustomerIdentity(
                customer_id=customer_id,
                is_new_customer=True,
                email=email,
                phone=phone,
            )

        # Get channel history for existing customer
        hist_result = await db_session.execute(
            text(
                "SELECT DISTINCT origin_channel FROM tickets WHERE customer_id = :cid"
            ),
            {"cid": customer.id},
        )
        channels = [row[0] for row in hist_result.fetchall()]

        count_result = await db_session.execute(
            text("SELECT COUNT(*) FROM tickets WHERE customer_id = :cid"),
            {"cid": customer.id},
        )
        ticket_count = count_result.scalar() or 0

        return CustomerIdentity(
            customer_id=str(customer.id),
            is_new_customer=False,
            email=customer.email,
            phone=customer.phone,
            previous_channels=channels,
            ticket_count=ticket_count,
        )

    def _mock_resolve(
        self, email: Optional[str], phone: Optional[str], name: Optional[str]
    ) -> CustomerIdentity:
        """Mock resolution for testing without DB."""
        customer_id = email or phone or "anonymous"
        return CustomerIdentity(
            customer_id=customer_id,
            is_new_customer=True,
            email=email,
            phone=phone,
        )


# ─── Skills Registry ──────────────────────────────────────────────────────────

SKILLS = {
    "knowledge_retrieval": KnowledgeRetrievalSkill(),
    "sentiment_analysis": SentimentAnalysisSkill(),
    "escalation_decision": EscalationDecisionSkill(),
    "channel_adaptation": ChannelAdaptationSkill(),
    "customer_identification": CustomerIdentificationSkill(),
}

SKILLS_MANIFEST = {
    "version": "1.0",
    "agent": "FlowForge Customer Success FTE",
    "skills": [
        {
            "name": skill.name,
            "description": skill.description,
            "class": skill.__class__.__name__,
        }
        for skill in SKILLS.values()
    ],
}
