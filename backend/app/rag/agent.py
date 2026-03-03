from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Literal, Sequence

from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain.tools import tool
from pydantic import BaseModel, Field

from ..core.config import settings
from .embeddings import get_chat_model
from .memory import MemoryTurn, format_history_for_prompt
from .prompts import (
    GROUNDED_REGEN_PROMPT,
    INSUFFICIENT_CONTEXT_RESPONSE,
    SYSTEM_GROUNDED_PROMPT,
)
from .retriever import AgenticRetriever, RetrievedChunk, RetrievalBundle

logger = logging.getLogger(__name__)

Confidence = Literal["high", "medium", "low"]


class AgentOutput(BaseModel):
    answer: str = Field(min_length=1)
    citations: list[str] = Field(default_factory=list)
    confidence: Confidence = "low"


@dataclass(slots=True)
class ToolRuntimeState:
    tool_calls: list[str] = field(default_factory=list)
    vector_chunks: list[RetrievedChunk] = field(default_factory=list)
    memory_chunks: list[RetrievedChunk] = field(default_factory=list)
    metadata_scope: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class AgentExecutionResult:
    answer: str
    citations: list[str]
    confidence: Confidence
    tool_calls: list[str]
    rewritten_query: str


class AgenticRAGAgent:
    def __init__(self, retriever: AgenticRetriever) -> None:
        self._retriever = retriever
        self._agent_model = None
        self._regen_model = None

    async def answer(
        self,
        *,
        message: str,
        tenant_id: str,
        device_id: str,
        history_turns: Sequence[MemoryTurn],
        top_k: int,
    ) -> AgentExecutionResult:
        baseline_bundle = await self._retriever.retrieve_context(
            question=message,
            tenant_id=tenant_id,
            device_id=device_id,
            history_turns=history_turns,
            top_k=top_k,
            similarity_threshold=settings.AGENTIC_SIMILARITY_THRESHOLD,
            doc_types=("knowledge",),
            apply_compression=True,
        )
        baseline_memory = await self._retriever.retrieve_context(
            question=message,
            tenant_id=tenant_id,
            device_id=device_id,
            history_turns=history_turns,
            top_k=max(1, settings.AGENTIC_LONG_MEMORY_TOP_K),
            similarity_threshold=0.0,
            doc_types=("memory",),
            apply_compression=False,
        )

        if not baseline_bundle.threshold_passed and not baseline_memory.chunks:
            return AgentExecutionResult(
                answer=INSUFFICIENT_CONTEXT_RESPONSE,
                citations=[],
                confidence="low",
                tool_calls=[],
                rewritten_query=baseline_bundle.rewritten_question,
            )

        runtime_state = ToolRuntimeState(
            vector_chunks=list(baseline_bundle.chunks),
            memory_chunks=list(baseline_memory.chunks),
            metadata_scope={"tenant_id": tenant_id, "device_id": device_id},
        )
        self._ensure_models()
        assert self._agent_model is not None
        tools = self._build_tools(
            tenant_id=tenant_id,
            device_id=device_id,
            history_turns=history_turns,
            runtime_state=runtime_state,
            top_k=top_k,
        )

        agent = create_agent(
            model=self._agent_model,
            tools=tools,
            system_prompt=(
                f"{SYSTEM_GROUNDED_PROMPT}\n\n"
                "Execution requirements:\n"
                "- Use MetadataFilterTool first to confirm the tenant/device scope.\n"
                "- Use VectorSearchTool before concluding anything factual.\n"
                "- Use ConversationMemoryTool when follow-up context may matter.\n"
                "- Never output hidden reasoning, only the final answer.\n"
            ),
            middleware=[
                ToolCallLimitMiddleware(
                    run_limit=max(1, settings.AGENTIC_MAX_TOOL_STEPS),
                    exit_behavior="continue",
                )
            ],
            response_format=AgentOutput,
            name="trustseal_agentic_rag",
            debug=False,
        )

        history_text = format_history_for_prompt(history_turns[-settings.AGENTIC_SHORT_MEMORY_WINDOW :])
        user_prompt = (
            "Answer this operational question using grounded retrieval.\n"
            f"Question: {message}\n\n"
            f"Conversation history:\n{history_text or 'No prior conversation.'}\n"
        )

        raw_result = await agent.ainvoke({"messages": [{"role": "user", "content": user_prompt}]})
        structured = raw_result.get("structured_response")
        if isinstance(structured, AgentOutput):
            answer_obj = structured
        elif isinstance(structured, dict):
            answer_obj = AgentOutput.model_validate(structured)
        else:
            answer_obj = AgentOutput(answer=INSUFFICIENT_CONTEXT_RESPONSE, citations=[], confidence="low")

        chunks_for_grounding = self._collect_grounding_chunks(
            baseline_bundle=baseline_bundle,
            baseline_memory=baseline_memory,
            runtime_state=runtime_state,
        )
        citations = self._normalize_citations(answer_obj.citations, chunks_for_grounding)
        answer_text = answer_obj.answer.strip()

        if not self._is_grounded(answer_text, citations, chunks_for_grounding):
            answer_text, citations = await self._regenerate_grounded_answer(
                question=message,
                chunks=chunks_for_grounding,
            )

        if not self._is_grounded(answer_text, citations, chunks_for_grounding):
            answer_text = INSUFFICIENT_CONTEXT_RESPONSE
            citations = []

        confidence = self._derive_confidence(chunks_for_grounding, citations)
        if answer_text == INSUFFICIENT_CONTEXT_RESPONSE:
            confidence = "low"

        self._log_reasoning_summary(runtime_state=runtime_state, citations=citations)
        return AgentExecutionResult(
            answer=answer_text,
            citations=citations,
            confidence=confidence,
            tool_calls=list(runtime_state.tool_calls),
            rewritten_query=baseline_bundle.rewritten_question,
        )

    def _build_tools(
        self,
        *,
        tenant_id: str,
        device_id: str,
        history_turns: Sequence[MemoryTurn],
        runtime_state: ToolRuntimeState,
        top_k: int,
    ) -> list[Any]:
        @tool("MetadataFilterTool")
        def metadata_filter_tool() -> dict[str, str]:
            """Return active metadata scope for strict multi-tenant/device retrieval."""
            runtime_state.tool_calls.append("MetadataFilterTool")
            runtime_state.metadata_scope = {"tenant_id": tenant_id, "device_id": device_id}
            return runtime_state.metadata_scope

        @tool("ConversationMemoryTool")
        async def conversation_memory_tool(query: str) -> dict[str, Any]:
            """Fetch short-term conversation memory and relevant long-term memory snippets."""
            runtime_state.tool_calls.append("ConversationMemoryTool")
            memory_bundle = await self._retriever.retrieve_context(
                question=query,
                tenant_id=tenant_id,
                device_id=device_id,
                history_turns=history_turns,
                top_k=max(1, settings.AGENTIC_LONG_MEMORY_TOP_K),
                similarity_threshold=0.0,
                doc_types=("memory",),
                apply_compression=False,
            )
            if memory_bundle.chunks:
                runtime_state.memory_chunks = memory_bundle.chunks
            history_text = format_history_for_prompt(history_turns[-settings.AGENTIC_SHORT_MEMORY_WINDOW :])
            return {
                "history": history_text or "No short-term history.",
                "long_term_memory": [
                    {
                        "source_id": chunk.source_id,
                        "snippet": chunk.content,
                        "score": chunk.score,
                    }
                    for chunk in runtime_state.memory_chunks
                ],
            }

        @tool("VectorSearchTool")
        async def vector_search_tool(query: str, top_k_override: int | None = None) -> dict[str, Any]:
            """Run semantic similarity + MMR search with metadata filters for grounded context."""
            runtime_state.tool_calls.append("VectorSearchTool")
            bundle = await self._retriever.retrieve_context(
                question=query,
                tenant_id=tenant_id,
                device_id=device_id,
                history_turns=history_turns,
                top_k=max(1, top_k_override or top_k),
                similarity_threshold=settings.AGENTIC_SIMILARITY_THRESHOLD,
                doc_types=("knowledge",),
                apply_compression=True,
            )
            if bundle.chunks:
                runtime_state.vector_chunks = bundle.chunks
            return {
                "rewritten_query": bundle.rewritten_question,
                "threshold_passed": bundle.threshold_passed,
                "max_similarity": bundle.max_similarity,
                "matches": [
                    {
                        "source_id": chunk.source_id,
                        "snippet": chunk.content,
                        "score": chunk.score,
                    }
                    for chunk in bundle.chunks
                ],
            }

        return [metadata_filter_tool, conversation_memory_tool, vector_search_tool]

    def _collect_grounding_chunks(
        self,
        *,
        baseline_bundle: RetrievalBundle,
        baseline_memory: RetrievalBundle,
        runtime_state: ToolRuntimeState,
    ) -> list[RetrievedChunk]:
        by_source: dict[str, RetrievedChunk] = {}
        for chunk in baseline_bundle.chunks:
            by_source[chunk.source_id] = chunk
        for chunk in baseline_memory.chunks:
            by_source[chunk.source_id] = chunk
        for chunk in runtime_state.vector_chunks:
            by_source[chunk.source_id] = chunk
        for chunk in runtime_state.memory_chunks:
            by_source[chunk.source_id] = chunk
        return list(by_source.values())

    def _normalize_citations(
        self,
        citations: Sequence[str],
        chunks: Sequence[RetrievedChunk],
    ) -> list[str]:
        allowed = {chunk.source_id for chunk in chunks}
        unique: list[str] = []
        for citation in citations:
            candidate = str(citation).strip()
            if candidate and candidate in allowed and candidate not in unique:
                unique.append(candidate)
        if unique:
            return unique
        return [chunk.source_id for chunk in chunks[:3]]

    async def _regenerate_grounded_answer(
        self,
        *,
        question: str,
        chunks: Sequence[RetrievedChunk],
    ) -> tuple[str, list[str]]:
        if not chunks:
            return INSUFFICIENT_CONTEXT_RESPONSE, []
        self._ensure_models()
        assert self._regen_model is not None
        evidence = "\n\n".join(
            f"source_id={chunk.source_id}\nsnippet={chunk.content}"
            for chunk in chunks
        )
        prompt = (
            f"{GROUNDED_REGEN_PROMPT}\n\n"
            f"Question:\n{question}\n\n"
            f"Evidence snippets:\n{evidence}\n\n"
            "Return a grounded answer in the 4-part operational format."
        )
        response = await self._regen_model.ainvoke(prompt)
        text = str(getattr(response, "content", "")).strip() or INSUFFICIENT_CONTEXT_RESPONSE
        citations = [chunk.source_id for chunk in chunks[:3]]
        return text, citations

    def _is_grounded(
        self,
        answer: str,
        citations: Sequence[str],
        chunks: Sequence[RetrievedChunk],
    ) -> bool:
        normalized_answer = answer.strip()
        if normalized_answer == INSUFFICIENT_CONTEXT_RESPONSE:
            return True
        if not chunks:
            return False

        by_source = {chunk.source_id: chunk for chunk in chunks}
        selected_chunks = [by_source[c] for c in citations if c in by_source] if citations else list(chunks)
        if not selected_chunks:
            return False

        answer_tokens = self._tokenize(normalized_answer)
        if len(answer_tokens) < 4:
            return False

        best_overlap = 0.0
        for chunk in selected_chunks:
            chunk_tokens = self._tokenize(chunk.content)
            if not chunk_tokens:
                continue
            overlap = len(answer_tokens.intersection(chunk_tokens)) / max(1, len(answer_tokens))
            best_overlap = max(best_overlap, overlap)
        return best_overlap >= 0.12

    def _derive_confidence(self, chunks: Sequence[RetrievedChunk], citations: Sequence[str]) -> Confidence:
        if not chunks:
            return "low"
        top_score = max((chunk.score for chunk in chunks), default=0.0)
        if citations and top_score >= 0.8:
            return "high"
        if top_score >= 0.62:
            return "medium"
        return "low"

    def _tokenize(self, text: str) -> set[str]:
        return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2}

    def _log_reasoning_summary(
        self,
        *,
        runtime_state: ToolRuntimeState,
        citations: Sequence[str],
    ) -> None:
        logger.info(
            "Agent run completed tools=%s citations=%s scope=%s",
            runtime_state.tool_calls,
            list(citations),
            runtime_state.metadata_scope,
        )

    def _ensure_models(self) -> None:
        if self._agent_model is None:
            self._agent_model = get_chat_model(
                temperature=min(settings.AGENTIC_TEMPERATURE, 0.3),
                max_tokens=settings.AGENTIC_MAX_RESPONSE_TOKENS,
            )
        if self._regen_model is None:
            self._regen_model = get_chat_model(
                temperature=0.0,
                max_tokens=settings.AGENTIC_MAX_RESPONSE_TOKENS,
            )
