from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_postgres import PGVector
from langchain_postgres.vectorstores import DistanceStrategy

from ..core.config import settings
from .database import AsyncDocumentRepository, DocumentRow
from .embeddings import get_chat_model, get_embeddings_client
from .memory import MemoryTurn, format_history_for_prompt
from .prompts import CONTEXT_COMPRESSION_PROMPT, QUESTION_REWRITE_PROMPT

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RetrievedChunk:
    source_id: str
    content: str
    score: float
    metadata: dict[str, Any]


@dataclass(slots=True)
class RetrievalBundle:
    original_question: str
    rewritten_question: str
    chunks: list[RetrievedChunk]
    max_similarity: float
    threshold_passed: bool


def _langchain_pg_dsn(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql+psycopg2://"):
        return database_url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    return database_url


def _safe_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(content or "")


class AgenticRetriever:
    def __init__(self, repository: AsyncDocumentRepository) -> None:
        self._repository = repository
        self._embeddings = None
        self._rewrite_model = None
        self._compress_model = None
        self._vector_store: PGVector | None = None
        self._init_lock = asyncio.Lock()

    async def initialize(self) -> None:
        if self._vector_store is not None:
            return

        async with self._init_lock:
            if self._vector_store is not None:
                return

            self._ensure_models()
            assert self._embeddings is not None
            self._vector_store = PGVector(
                embeddings=self._embeddings,
                connection=_langchain_pg_dsn(settings.DATABASE_URL),
                collection_name=settings.AGENTIC_VECTOR_COLLECTION,
                embedding_length=settings.RAG_EMBEDDING_DIMENSION,
                distance_strategy=DistanceStrategy.COSINE,
                use_jsonb=True,
                create_extension=True,
                async_mode=True,
            )
            await self._vector_store.acreate_collection()

    async def ingest_document(
        self,
        *,
        tenant_id: str,
        device_id: str,
        raw_document: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[str]:
        await self.initialize()
        if self._vector_store is None:
            return []
        assert self._embeddings is not None

        clean_document = raw_document.strip()
        if not clean_document:
            return []

        chunks = self._chunk_text(
            clean_document,
            chunk_size=settings.AGENTIC_CHUNK_SIZE,
            overlap=settings.AGENTIC_CHUNK_OVERLAP,
        )
        if not chunks:
            return []

        metadata = metadata or {}
        doc_type = str(metadata.get("doc_type", "knowledge"))
        source = str(metadata.get("source", "ingest"))
        chunk_ids = [str(uuid.uuid4()) for _ in chunks]

        all_embeddings: list[list[float]] = []
        for start in range(0, len(chunks), max(1, settings.AGENTIC_BATCH_SIZE)):
            batch = chunks[start : start + max(1, settings.AGENTIC_BATCH_SIZE)]
            batch_embeddings = await self._embeddings.aembed_documents(batch)
            all_embeddings.extend(batch_embeddings)

        enriched_metadatas: list[dict[str, Any]] = []
        document_rows: list[DocumentRow] = []
        for idx, (chunk_id, chunk_text, embedding) in enumerate(zip(chunk_ids, chunks, all_embeddings)):
            chunk_metadata = {
                "source_id": chunk_id,
                "tenant_id": tenant_id,
                "device_id": device_id,
                "doc_type": doc_type,
                "source": source,
                "chunk_index": idx,
                "chunk_count": len(chunks),
                **metadata,
            }
            enriched_metadatas.append(chunk_metadata)
            document_rows.append(
                DocumentRow(
                    id=chunk_id,
                    tenant_id=tenant_id,
                    device_id=device_id,
                    content=chunk_text,
                    metadata=chunk_metadata,
                    embedding=embedding,
                )
            )

        await self._repository.upsert_rows(document_rows)
        await self._vector_store.aadd_embeddings(
            texts=chunks,
            embeddings=all_embeddings,
            metadatas=enriched_metadatas,
            ids=chunk_ids,
        )

        return chunk_ids

    async def rewrite_question(
        self,
        *,
        question: str,
        history_turns: Sequence[MemoryTurn],
    ) -> str:
        if not history_turns:
            return question

        history = format_history_for_prompt(history_turns[-settings.AGENTIC_SHORT_MEMORY_WINDOW :])
        if not history:
            return question

        prompt = (
            f"{QUESTION_REWRITE_PROMPT}\n\n"
            f"Conversation history:\n{history}\n\n"
            f"Latest user question:\n{question}\n\n"
            "Standalone rewritten question:"
        )
        try:
            self._ensure_models()
            assert self._rewrite_model is not None
            message = await self._rewrite_model.ainvoke(
                [SystemMessage(content=QUESTION_REWRITE_PROMPT), HumanMessage(content=prompt)]
            )
            rewritten = _safe_text(message.content).strip()
            return rewritten or question
        except Exception:
            logger.exception("Question rewrite failed; falling back to original question.")
            return question

    async def retrieve_context(
        self,
        *,
        question: str,
        tenant_id: str,
        device_id: str,
        history_turns: Sequence[MemoryTurn],
        top_k: int | None = None,
        similarity_threshold: float | None = None,
        doc_types: Sequence[str] = ("knowledge",),
        apply_compression: bool = True,
    ) -> RetrievalBundle:
        await self.initialize()
        if self._vector_store is None:
            return RetrievalBundle(
                original_question=question,
                rewritten_question=question,
                chunks=[],
                max_similarity=0.0,
                threshold_passed=False,
            )

        rewritten_question = await self.rewrite_question(
            question=question,
            history_turns=history_turns,
        )

        k = max(1, top_k or settings.AGENTIC_TOP_K)
        threshold = (
            settings.AGENTIC_SIMILARITY_THRESHOLD
            if similarity_threshold is None
            else similarity_threshold
        )

        metadata_filter: dict[str, Any] = {"tenant_id": tenant_id}
        if device_id and device_id != "*":
            metadata_filter["device_id"] = device_id
        if len(doc_types) == 1:
            metadata_filter["doc_type"] = doc_types[0]
        elif doc_types:
            metadata_filter["doc_type"] = {"$in": list(doc_types)}

        similarity_hits = await self._vector_store.asimilarity_search_with_relevance_scores(
            rewritten_question,
            k=k,
            filter=metadata_filter,
        )
        max_similarity = max((float(score) for _, score in similarity_hits), default=0.0)
        threshold_passed = max_similarity >= threshold
        if not threshold_passed:
            return RetrievalBundle(
                original_question=question,
                rewritten_question=rewritten_question,
                chunks=[],
                max_similarity=max_similarity,
                threshold_passed=False,
            )

        mmr_hits = await self._vector_store.amax_marginal_relevance_search_with_score(
            rewritten_question,
            k=k,
            fetch_k=max(k, settings.AGENTIC_MMR_FETCH_K),
            lambda_mult=settings.AGENTIC_MMR_LAMBDA,
            filter=metadata_filter,
        )

        chunks: list[RetrievedChunk] = []
        for document, distance in mmr_hits:
            metadata = dict(document.metadata or {})
            source_id = str(metadata.get("source_id") or document.id or "")
            if not source_id:
                source_id = str(uuid.uuid4())
            chunks.append(
                RetrievedChunk(
                    source_id=source_id,
                    content=document.page_content,
                    score=self._distance_to_similarity(distance),
                    metadata=metadata,
                )
            )

        if apply_compression and chunks:
            chunks = await self._compress_chunks(question=rewritten_question, chunks=chunks)

        return RetrievalBundle(
            original_question=question,
            rewritten_question=rewritten_question,
            chunks=chunks,
            max_similarity=max_similarity,
            threshold_passed=True,
        )

    def _chunk_text(self, text: str, *, chunk_size: int, overlap: int) -> list[str]:
        body = text.strip()
        if not body:
            return []
        if len(body) <= chunk_size:
            return [body]

        chunks: list[str] = []
        step = max(1, chunk_size - max(0, overlap))
        for start in range(0, len(body), step):
            end = min(len(body), start + chunk_size)
            chunk = body[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(body):
                break
        return chunks

    async def _compress_chunks(self, *, question: str, chunks: Sequence[RetrievedChunk]) -> list[RetrievedChunk]:
        if not chunks:
            return []

        chunk_block = "\n\n".join(
            f"source_id={chunk.source_id}\ncontent={chunk.content}"
            for chunk in chunks
        )
        prompt = (
            f"{CONTEXT_COMPRESSION_PROMPT}\n\n"
            f"Question:\n{question}\n\n"
            f"Candidate chunks:\n{chunk_block}\n"
        )
        try:
            self._ensure_models()
            assert self._compress_model is not None
            response = await self._compress_model.ainvoke(
                [SystemMessage(content=CONTEXT_COMPRESSION_PROMPT), HumanMessage(content=prompt)]
            )
            response_text = _safe_text(response.content).strip()
            parsed = self._extract_json(response_text)
            items = parsed.get("items", []) if isinstance(parsed, dict) else []
            if not isinstance(items, list):
                return list(chunks)

            by_source_id = {chunk.source_id: chunk for chunk in chunks}
            compressed: list[RetrievedChunk] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                source_id = str(item.get("source_id") or "").strip()
                snippet = str(item.get("snippet") or "").strip()
                original = by_source_id.get(source_id)
                if not source_id or not snippet or original is None:
                    continue
                compressed.append(
                    RetrievedChunk(
                        source_id=source_id,
                        content=snippet,
                        score=original.score,
                        metadata=original.metadata,
                    )
                )
            return compressed or list(chunks)
        except Exception:
            logger.exception("Context compression failed; using raw chunks.")
            return list(chunks)

    def _extract_json(self, text: str) -> dict[str, Any]:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            return {}
        candidate = text[start : end + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {}
        return {}

    def _distance_to_similarity(self, distance: float) -> float:
        try:
            value = float(distance)
        except (TypeError, ValueError):
            return 0.0
        # For cosine distance in [0, 2], map to [0, 1].
        similarity = 1.0 - max(0.0, min(1.0, value))
        return round(similarity, 4)

    def _ensure_models(self) -> None:
        if self._embeddings is None:
            self._embeddings = get_embeddings_client()
        if self._rewrite_model is None:
            self._rewrite_model = get_chat_model(temperature=0.0, max_tokens=220)
        if self._compress_model is None:
            self._compress_model = get_chat_model(temperature=0.0, max_tokens=380)
