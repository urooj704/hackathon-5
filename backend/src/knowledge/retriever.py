"""
Knowledge Base Retriever — semantic search via pgvector.

Given a query string, embed it and find the top-K most similar doc chunks.
Results are used to inject relevant product documentation into the agent's context.
"""

from typing import List

import structlog
from openai import AsyncOpenAI
from pgvector.sqlalchemy import Vector
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db.models import DocChunk

log = structlog.get_logger(__name__)
settings = get_settings()

_openai_client: AsyncOpenAI | None = None


def _get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _openai_client


async def embed_query(query: str) -> List[float]:
    """Embed a single query string."""
    client = _get_openai_client()
    response = await client.embeddings.create(
        model=settings.embedding_model,
        input=query,
        dimensions=settings.embedding_dimensions,
    )
    return response.data[0].embedding


async def search_docs(
    db: AsyncSession,
    query: str,
    top_k: int = 4,
    min_score: float = 0.70,
) -> List[dict]:
    """
    Semantic search over the knowledge base.

    Args:
        db: Async DB session
        query: Natural language query from the agent
        top_k: Maximum number of results to return
        min_score: Minimum cosine similarity (0–1); lower = less relevant

    Returns:
        List of dicts: {section_title, content, score}
    """
    query_embedding = await embed_query(query)

    # pgvector cosine similarity: 1 - cosine_distance
    # sqlalchemy pgvector operator: <=> is cosine distance
    result = await db.execute(
        select(
            DocChunk.section_title,
            DocChunk.content,
            (1 - DocChunk.embedding.cosine_distance(query_embedding)).label("score"),
        )
        .where(DocChunk.embedding.isnot(None))
        .order_by(DocChunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )

    rows = result.all()

    chunks = [
        {
            "section_title": row.section_title,
            "content": row.content,
            "score": float(row.score),
        }
        for row in rows
        if float(row.score) >= min_score
    ]

    log.info(
        "docs_searched",
        query=query[:80],
        results_found=len(chunks),
        top_score=chunks[0]["score"] if chunks else None,
    )

    return chunks


def format_docs_for_prompt(chunks: List[dict]) -> str:
    """
    Format retrieved doc chunks into a clean string for the agent's context window.
    """
    if not chunks:
        return "No relevant documentation found."

    parts = []
    for i, chunk in enumerate(chunks, 1):
        parts.append(
            f"[Doc {i}: {chunk['section_title']}]\n{chunk['content']}"
        )

    return "\n\n---\n\n".join(parts)
