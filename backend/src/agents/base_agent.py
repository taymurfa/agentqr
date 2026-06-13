"""Base agent class with RAG capabilities, Claude LLM, and tool use."""

import time
import uuid
from typing import Optional, AsyncIterator
from pathlib import Path
from abc import ABC, abstractmethod

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import get_settings
from src.knowledge_base.vector_store import VectorStore
from src.knowledge_base.embeddings import EmbeddingGenerator
from src.database.models import AgentLog


class BaseAgent(ABC):
    """Base class for all RAG-enabled research agents."""

    def __init__(self, db: AsyncSession, agent_name: str):
        self.settings = get_settings()
        self.db = db
        self.agent_name = agent_name
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        self.vector_store = VectorStore()
        self.embedder = EmbeddingGenerator()
        self.system_prompt = self._load_system_prompt()
        self.conversation_history: list[dict] = []

    def _load_system_prompt(self) -> str:
        """Load the agent's system prompt from the prompts directory."""
        prompt_map = {
            "orchestrator": "orchestrator.md",
            "sector_researcher": "sector_researcher.md",
            "technical_analyst": "technical_analyst.md",
            "fundamental_analyst": "fundamental_analyst.md",
        }
        filename = prompt_map.get(self.agent_name, f"{self.agent_name}.md")
        prompt_path = Path(__file__).parent.parent.parent / "config" / "prompts" / filename

        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return f"You are the {self.agent_name} agent."

    async def rag_query(
        self,
        query: str,
        namespace: Optional[str] = None,
        top_k: int = 10,
        filter: Optional[dict] = None,
    ) -> list[dict]:
        """Perform RAG retrieval: embed query and search vector store.
        Returns empty list if embeddings are unavailable (rate limited)."""
        query_embedding = self.embedder.embed_query(query)
        if query_embedding is None:
            return []  # Graceful degradation when Voyage AI is rate limited

        try:
            results = self.vector_store.query(
                vector=query_embedding,
                top_k=top_k,
                namespace=namespace,
                filter=filter,
                include_metadata=True,
            )
            return results
        except Exception as e:
            print(f"[{self.agent_name}] Vector query failed: {e}")
            return []

    def build_context(self, rag_results: list[dict]) -> str:
        """Build context string from RAG results for the LLM prompt."""
        if not rag_results:
            return "No relevant documents found in the knowledge base."

        context_parts = []
        for i, result in enumerate(rag_results, 1):
            meta = result.get("metadata", {})
            source = meta.get("source", "unknown")
            ticker = meta.get("ticker", "")
            doc_type = meta.get("document_type", meta.get("filing_type", ""))
            date = meta.get("filing_date", meta.get("published_date", meta.get("date", "")))
            text = meta.get("text", "")

            header = f"[Source {i}] {source}"
            if ticker:
                header += f" | {ticker}"
            if doc_type:
                header += f" | {doc_type}"
            if date:
                header += f" | {date}"

            context_parts.append(f"{header}\n{text}")

        return "\n\n---\n\n".join(context_parts)

    async def call_llm(
        self,
        user_message: str,
        context: str = "",
        extra_system: str = "",
        max_tokens: int = 4096,
    ) -> str:
        """Call OpenAI with context and return the response."""
        system = self.system_prompt
        if extra_system:
            system += f"\n\n{extra_system}"
        if context:
            system += f"\n\n## Retrieved Research Context\n\n{context}"

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": user_message})

        start = time.time()
        response = await self.client.chat.completions.create(
            model=self.settings.openai_model,
            max_tokens=max_tokens,
            messages=messages,
        )
        latency = int((time.time() - start) * 1000)

        content = response.choices[0].message.content or ""
        tokens = response.usage.total_tokens if response.usage else 0

        self.conversation_history.append({"role": "user", "content": user_message})
        self.conversation_history.append({"role": "assistant", "content": content})

        await self._log("completed", f"LLM call for: {user_message[:100]}",
                        tokens_used=tokens, latency_ms=latency)

        return content

    async def stream_llm(
        self,
        user_message: str,
        context: str = "",
        extra_system: str = "",
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Stream OpenAI response token by token."""
        system = self.system_prompt
        if extra_system:
            system += f"\n\n{extra_system}"
        if context:
            system += f"\n\n## Retrieved Research Context\n\n{context}"

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": user_message})

        full_response = ""
        stream = await self.client.chat.completions.create(
            model=self.settings.openai_model,
            max_tokens=max_tokens,
            messages=messages,
            stream=True,
        )
        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                full_response += content
                yield content

        self.conversation_history.append({"role": "user", "content": user_message})
        self.conversation_history.append({"role": "assistant", "content": full_response})

    @abstractmethod
    async def run(self, query: str, **kwargs) -> dict:
        """Execute the agent's primary task. Must be implemented by subclasses."""
        pass

    async def generate_summary(self, content: str, max_length: int = 500) -> str:
        """Generate a compressed summary for context window management."""
        prompt = (
            f"Summarize the following research content in {max_length} words or less. "
            f"Focus on the most critical findings, numbers, and actionable insights:\n\n{content}"
        )
        return await self.call_llm(prompt, max_tokens=1024)

    async def _log(
        self,
        status: str,
        message: str,
        tokens_used: int = 0,
        latency_ms: int = 0,
        input_data: dict = None,
        output_data: dict = None,
    ):
        """Write an agent activity log (best-effort, won't crash the pipeline)."""
        try:
            log = AgentLog(
                id=uuid.uuid4(),
                job_id=str(uuid.uuid4())[:8],
                agent_name=self.agent_name,
                status=status,
                message=message,
                tokens_used=tokens_used,
                latency_ms=latency_ms,
                input_data=input_data,
                output_data=output_data,
            )
            self.db.add(log)
            await self.db.commit()
        except Exception as e:
            # Don't let logging failures crash the research pipeline
            try:
                await self.db.rollback()
            except Exception:
                pass
            print(f"[{self.agent_name}] Log write failed (non-fatal): {e}")

