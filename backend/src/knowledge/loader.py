"""
Knowledge Base Loader.

Reads product-docs.md, splits it into semantic chunks, embeds each chunk
using OpenAI text-embedding-3-small, and upserts into the doc_chunks table.

Run at startup (if table is empty) or manually via CLI to re-index.
"""

import hashlib
import re
from pathlib import Path
from typing import List, Tuple

import structlog
from openai import AsyncOpenAI
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db.models import DocChunk

log = structlog.get_logger(__name__)
settings = get_settings()

DOCS_PATH = Path(__file__).parent.parent.parent / "context" / "product-docs.md"
CHUNK_SIZE = 600     # max characters per chunk
CHUNK_OVERLAP = 100  # overlap between adjacent chunks


def _split_by_sections(text: str) -> List[Tuple[str, str]]:
    """
    Split markdown document into (section_title, content) pairs.
    Splits on ## and ### headers.
    Returns list of (title, body) tuples.
    """
    pattern = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
    matches = list(pattern.finditer(text))

    sections = []
    for i, match in enumerate(matches):
        title = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            sections.append((title, body))

    return sections


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Split a long text into overlapping chunks by character count.
    Tries to split on paragraph boundaries first.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    paragraphs = text.split("\n\n")
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= chunk_size:
            current = f"{current}\n\n{para}".strip()
        else:
            if current:
                chunks.append(current)
            # If single paragraph > chunk_size, hard split
            if len(para) > chunk_size:
                for i in range(0, len(para), chunk_size - overlap):
                    chunks.append(para[i : i + chunk_size])
            else:
                current = para

    if current:
        chunks.append(current)

    return chunks


async def _embed_texts(client: AsyncOpenAI, texts: List[str]) -> List[List[float]]:
    """Batch embed texts using OpenAI API."""
    # OpenAI allows up to 2048 inputs per request
    all_embeddings = []
    batch_size = 100

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = await client.embeddings.create(
            model=settings.embedding_model,
            input=batch,
            dimensions=settings.embedding_dimensions,
        )
        all_embeddings.extend([item.embedding for item in response.data])

    return all_embeddings


async def load_knowledge_base(db: AsyncSession, force_reload: bool = False) -> int:
    """
    Load product-docs.md into the doc_chunks table.

    Args:
        db: Async DB session
        force_reload: If True, clears existing chunks and reloads from scratch

    Returns:
        Number of chunks loaded
    """
    if not DOCS_PATH.exists():
        log.error("docs_file_not_found", path=str(DOCS_PATH))
        return 0

    # Check if already loaded
    if not force_reload:
        result = await db.execute(select(DocChunk.id).limit(1))
        if result.scalar_one_or_none() is not None:
            log.info("knowledge_base_already_loaded", skipping=True)
            return 0

    if force_reload:
        await db.execute(delete(DocChunk))
        await db.flush()
        log.info("knowledge_base_cleared")

    # Read and parse docs
    raw_text = DOCS_PATH.read_text(encoding="utf-8")
    sections = _split_by_sections(raw_text)

    log.info("docs_parsed", sections=len(sections))

    # Build chunks
    all_chunks: List[Tuple[str, str, int]] = []  # (section_title, chunk_text, chunk_index)
    for title, body in sections:
        chunks = _chunk_text(body)
        for idx, chunk in enumerate(chunks):
            all_chunks.append((title, chunk, idx))

    log.info("chunks_prepared", count=len(all_chunks))

    # Embed all chunks (skip if OpenAI key is missing/placeholder)
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    texts_to_embed = [f"{title}\n\n{chunk}" for title, chunk, _ in all_chunks]

    log.info("embedding_chunks", count=len(texts_to_embed))
    try:
        embeddings = await _embed_texts(openai_client, texts_to_embed)
    except Exception as exc:
        log.warning("embedding_failed_storing_without_vectors", error=str(exc))
        embeddings = [None] * len(all_chunks)

    # Upsert into DB
    for (title, chunk, chunk_idx), embedding in zip(all_chunks, embeddings):
        doc_chunk = DocChunk(
            source_file="product-docs.md",
            section_title=title,
            content=chunk,
            chunk_index=chunk_idx,
            embedding=embedding,
            tags=_infer_tags(title, chunk),
        )
        db.add(doc_chunk)

    await db.flush()
    log.info("knowledge_base_loaded", chunks_inserted=len(all_chunks))
    return len(all_chunks)


def _infer_tags(title: str, content: str) -> List[str]:
    """Infer topic tags from section title and content for optional filtering."""
    tags = []
    title_lower = title.lower()
    content_lower = content.lower()

    tag_keywords = {
        "billing": ["billing", "invoice", "payment", "refund", "charge", "plan", "pricing"],
        "gmail": ["gmail", "google workspace", "email trigger"],
        "slack": ["slack", "message"],
        "hubspot": ["hubspot", "crm"],
        "airtable": ["airtable"],
        "stripe": ["stripe", "payment"],
        "webhook": ["webhook", "http", "outgoing"],
        "authentication": ["auth", "oauth", "api key", "token", "401"],
        "error_handling": ["error", "retry", "failed", "404", "429", "413"],
        "scheduler": ["schedule", "cron", "interval"],
        "team": ["team", "sso", "permission", "role", "member"],
        "trial": ["trial", "free"],
        "security": ["security", "gdpr", "compliance", "encryption", "soc2"],
        "limits": ["limit", "quota", "task", "workflow cap"],
        "ai": ["flowforge ai", "natural language", "beta"],
    }

    for tag, keywords in tag_keywords.items():
        if any(kw in title_lower or kw in content_lower for kw in keywords):
            tags.append(tag)

    return tags
