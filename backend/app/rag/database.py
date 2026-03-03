from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Iterable

from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from ..core.config import settings


def normalize_pg_dsn(database_url: str) -> str:
    if database_url.startswith("postgresql+psycopg://"):
        return database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    if database_url.startswith("postgresql+psycopg2://"):
        return database_url.replace("postgresql+psycopg2://", "postgresql://", 1)
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return database_url


def embedding_to_vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in embedding) + "]"


@dataclass(slots=True)
class DocumentRow:
    id: str
    tenant_id: str
    device_id: str
    content: str
    metadata: dict[str, Any]
    embedding: list[float]


class AsyncDocumentRepository:
    def __init__(self) -> None:
        dsn = normalize_pg_dsn(settings.DATABASE_URL)
        self._pool = AsyncConnectionPool(
            conninfo=dsn,
            min_size=max(1, settings.AGENTIC_POOL_MIN_SIZE),
            max_size=max(settings.AGENTIC_POOL_MIN_SIZE, settings.AGENTIC_POOL_MAX_SIZE),
            timeout=5,
            open=False,
        )

    async def open(self) -> None:
        await self._pool.open(wait=True)

    async def close(self) -> None:
        await self._pool.close()

    async def healthcheck(self) -> bool:
        try:
            async with self._pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")
                    row = await cur.fetchone()
            return bool(row and row[0] == 1)
        except Exception:
            return False

    async def upsert_rows(self, rows: Iterable[DocumentRow]) -> list[str]:
        payload = list(rows)
        if not payload:
            return []

        sql = """
        INSERT INTO documents (id, tenant_id, device_id, content, metadata, embedding)
        VALUES (%s, %s, %s, %s, %s, %s::vector)
        ON CONFLICT (id) DO UPDATE
        SET tenant_id = EXCLUDED.tenant_id,
            device_id = EXCLUDED.device_id,
            content = EXCLUDED.content,
            metadata = EXCLUDED.metadata,
            embedding = EXCLUDED.embedding
        """

        params: list[tuple[Any, ...]] = []
        for row in payload:
            params.append(
                (
                    uuid.UUID(str(row.id)),
                    row.tenant_id,
                    row.device_id,
                    row.content,
                    Jsonb(row.metadata),
                    embedding_to_vector_literal(row.embedding),
                )
            )

        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.executemany(sql, params)
            await conn.commit()

        return [row.id for row in payload]
