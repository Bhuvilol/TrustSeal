from pydantic_settings import BaseSettings
from typing import Optional, List
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")
DEFAULT_CHAIN_ABI_PATH = ROOT_DIR.parent / "contract" / "artifacts" / "contracts" / "SupplyChainRelay.sol" / "SupplyChainRelay.json"

class Settings(BaseSettings):
    PROJECT_NAME: str = "TrustSeal IoT"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    VERIFICATION_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("VERIFICATION_TOKEN_EXPIRE_MINUTES", "60"))
    BACKEND_CORS_ORIGINS: str = os.getenv(
        "BACKEND_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,https://trust-seal-git-main-pritamprayasbehera-9760s-projects.vercel.app,https://trust-seal-tawny.vercel.app",
    )
    BACKEND_CORS_ORIGIN_REGEX: Optional[str] = os.getenv("BACKEND_CORS_ORIGIN_REGEX")
    DATABASE_URL_OVERRIDE: Optional[str] = os.getenv("DATABASE_URL")
    
    # Database
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "trustseal")
    POSTGRES_PORT: Optional[int] = os.getenv("POSTGRES_PORT", 5432)
    POSTGRES_SSLMODE: Optional[str] = os.getenv("POSTGRES_SSLMODE", "prefer")
    SQLALCHEMY_POOL_SIZE: int = int(os.getenv("SQLALCHEMY_POOL_SIZE", "4"))
    SQLALCHEMY_MAX_OVERFLOW: int = int(os.getenv("SQLALCHEMY_MAX_OVERFLOW", "2"))
    SQLALCHEMY_POOL_TIMEOUT_SECONDS: int = int(os.getenv("SQLALCHEMY_POOL_TIMEOUT_SECONDS", "15"))
    SQLALCHEMY_POOL_RECYCLE_SECONDS: int = int(os.getenv("SQLALCHEMY_POOL_RECYCLE_SECONDS", "1800"))
    SQLALCHEMY_POOL_PRE_PING: bool = os.getenv("SQLALCHEMY_POOL_PRE_PING", "true").lower() == "true"
    POSTGRES_CONNECT_TIMEOUT_SECONDS: int = int(os.getenv("POSTGRES_CONNECT_TIMEOUT_SECONDS", "5"))
    WS_REQUIRE_AUTH: bool = os.getenv("WS_REQUIRE_AUTH", "false").lower() == "true"
    REALTIME_QUEUE_MAXSIZE: int = int(os.getenv("REALTIME_QUEUE_MAXSIZE", "5000"))
    TELEMETRY_PIPELINE_MODE: str = os.getenv("TELEMETRY_PIPELINE_MODE", "dual").lower()
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    REDIS_TELEMETRY_STREAM: str = os.getenv("REDIS_TELEMETRY_STREAM", "telemetry_stream")
    REDIS_CUSTODY_STREAM: str = os.getenv("REDIS_CUSTODY_STREAM", "custody_stream")
    REDIS_BUNDLE_READY_STREAM: str = os.getenv("REDIS_BUNDLE_READY_STREAM", "bundle_ready_stream")
    REDIS_ANCHOR_REQUEST_STREAM: str = os.getenv("REDIS_ANCHOR_REQUEST_STREAM", "anchor_request_stream")
    REDIS_TELEMETRY_CONSUMER_GROUP: str = os.getenv("REDIS_TELEMETRY_CONSUMER_GROUP", "batch_workers")
    REDIS_TELEMETRY_CONSUMER_NAME: str = os.getenv("REDIS_TELEMETRY_CONSUMER_NAME", "worker-1")
    REDIS_TELEMETRY_READ_COUNT: int = int(os.getenv("REDIS_TELEMETRY_READ_COUNT", "200"))
    REDIS_TELEMETRY_BLOCK_MS: int = int(os.getenv("REDIS_TELEMETRY_BLOCK_MS", "1000"))
    REDIS_RETRY_MAX_ATTEMPTS: int = int(os.getenv("REDIS_RETRY_MAX_ATTEMPTS", "5"))
    REDIS_RETRY_BASE_DELAY_MS: int = int(os.getenv("REDIS_RETRY_BASE_DELAY_MS", "500"))
    REDIS_RETRY_MAX_DELAY_MS: int = int(os.getenv("REDIS_RETRY_MAX_DELAY_MS", "30000"))
    REDIS_DEAD_LETTER_STREAM: str = os.getenv("REDIS_DEAD_LETTER_STREAM", "telemetry_dead_letter_stream")
    TELEMETRY_FINALIZATION_ENABLED: bool = os.getenv("TELEMETRY_FINALIZATION_ENABLED", "false").lower() == "true"
    BATCH_MIN_RECORDS: int = int(os.getenv("BATCH_MIN_RECORDS", "50"))
    BATCH_MAX_WINDOW_SECONDS: int = int(os.getenv("BATCH_MAX_WINDOW_SECONDS", "300"))
    BATCH_FORCE_ON_CUSTODY: bool = os.getenv("BATCH_FORCE_ON_CUSTODY", "true").lower() == "true"
    CUSTODY_GATE_MAX_AGE_SECONDS: int = int(os.getenv("CUSTODY_GATE_MAX_AGE_SECONDS", "1800"))
    INGEST_VERIFY_SIGNATURES: bool = os.getenv("INGEST_VERIFY_SIGNATURES", "false").lower() == "true"
    INGEST_DEVICE_AUTH_ENABLED: bool = os.getenv("INGEST_DEVICE_AUTH_ENABLED", "false").lower() == "true"
    INGEST_VERIFIER_AUTH_ENABLED: bool = os.getenv("INGEST_VERIFIER_AUTH_ENABLED", "false").lower() == "true"
    INGEST_DEVICE_TOKENS_JSON: Optional[str] = os.getenv("INGEST_DEVICE_TOKENS_JSON")
    INGEST_VERIFIER_TOKENS_JSON: Optional[str] = os.getenv("INGEST_VERIFIER_TOKENS_JSON")
    INGEST_DEVICE_PUBLIC_KEYS_JSON: Optional[str] = os.getenv("INGEST_DEVICE_PUBLIC_KEYS_JSON")
    INGEST_VERIFIER_PUBLIC_KEYS_JSON: Optional[str] = os.getenv("INGEST_VERIFIER_PUBLIC_KEYS_JSON")
    INGEST_REPLAY_MAX_CLOCK_SKEW_SECONDS: int = int(os.getenv("INGEST_REPLAY_MAX_CLOCK_SKEW_SECONDS", "300"))
    INGEST_REPLAY_MAX_EVENT_AGE_SECONDS: int = int(os.getenv("INGEST_REPLAY_MAX_EVENT_AGE_SECONDS", "86400"))
    ARCHIVE_HOT_RETENTION_DAYS: int = int(os.getenv("ARCHIVE_HOT_RETENTION_DAYS", "30"))
    ARCHIVE_COLD_RETENTION_DAYS: int = int(os.getenv("ARCHIVE_COLD_RETENTION_DAYS", "365"))
    ARCHIVE_PURGE_RETENTION_DAYS: int = int(os.getenv("ARCHIVE_PURGE_RETENTION_DAYS", "1095"))
    ARCHIVE_ENABLE_PURGE: bool = os.getenv("ARCHIVE_ENABLE_PURGE", "false").lower() == "true"
    IPFS_PIN_ENABLED: bool = os.getenv("IPFS_PIN_ENABLED", "false").lower() == "true"
    IPFS_PIN_ENDPOINT: str = os.getenv("IPFS_PIN_ENDPOINT", "https://api.pinata.cloud/pinning/pinJSONToIPFS")
    IPFS_PIN_JWT: Optional[str] = os.getenv("IPFS_PIN_JWT")
    CHAIN_ANCHOR_ENABLED: bool = os.getenv("CHAIN_ANCHOR_ENABLED", "false").lower() == "true"
    CHAIN_RPC_URL: Optional[str] = os.getenv("CHAIN_RPC_URL")
    CHAIN_CHAIN_ID: int = int(os.getenv("CHAIN_CHAIN_ID", "80002"))
    CHAIN_PRIVATE_KEY: Optional[str] = os.getenv("CHAIN_PRIVATE_KEY")
    CHAIN_CONTRACT_ADDRESS: Optional[str] = os.getenv("CHAIN_CONTRACT_ADDRESS")
    CHAIN_CONTRACT_ABI_JSON: Optional[str] = os.getenv("CHAIN_CONTRACT_ABI_JSON")
    CHAIN_CONTRACT_ABI_PATH: str = os.getenv("CHAIN_CONTRACT_ABI_PATH", str(DEFAULT_CHAIN_ABI_PATH))
    CHAIN_PREVIOUS_CUSTODIAN: str = os.getenv("CHAIN_PREVIOUS_CUSTODIAN", "0x0000000000000000000000000000000000000000")
    CHAIN_ANCHOR_MAX_ATTEMPTS: int = int(os.getenv("CHAIN_ANCHOR_MAX_ATTEMPTS", "3"))
    CHAIN_ANCHOR_RETRY_BASE_DELAY_MS: int = int(os.getenv("CHAIN_ANCHOR_RETRY_BASE_DELAY_MS", "1000"))
    CHAIN_ANCHOR_RETRY_MAX_DELAY_MS: int = int(os.getenv("CHAIN_ANCHOR_RETRY_MAX_DELAY_MS", "10000"))
    CHAIN_REPLACEMENT_GAS_BUMP_PERCENT: int = int(os.getenv("CHAIN_REPLACEMENT_GAS_BUMP_PERCENT", "15"))
    CHAIN_RECEIPT_TIMEOUT_SECONDS: int = int(os.getenv("CHAIN_RECEIPT_TIMEOUT_SECONDS", "120"))
    CHAIN_INDEXER_ENABLED: bool = os.getenv("CHAIN_INDEXER_ENABLED", "false").lower() == "true"
    CHAIN_INDEXER_START_BLOCK: int = int(os.getenv("CHAIN_INDEXER_START_BLOCK", "0"))
    CHAIN_INDEXER_BLOCK_BATCH_SIZE: int = int(os.getenv("CHAIN_INDEXER_BLOCK_BATCH_SIZE", "500"))
    CHAIN_INDEXER_CONFIRMATIONS: int = int(os.getenv("CHAIN_INDEXER_CONFIRMATIONS", "2"))

    OPENROUTER_API_KEY: Optional[str] = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-haiku")
    OPENROUTER_TIMEOUT_SECONDS: int = int(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "30"))
    OPENROUTER_MAX_TOKENS: int = int(os.getenv("OPENROUTER_MAX_TOKENS", "512"))
    OPENROUTER_SITE_URL: Optional[str] = os.getenv("OPENROUTER_SITE_URL")
    OPENROUTER_APP_NAME: str = os.getenv("OPENROUTER_APP_NAME", "TrustSeal IoT")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_BASE_URL: Optional[str] = os.getenv("OPENAI_BASE_URL")
    RAG_COLLECTION_NAME: str = os.getenv("RAG_COLLECTION_NAME", "trustseal_ops")
    RAG_EMBEDDING_MODEL: str = os.getenv("RAG_EMBEDDING_MODEL", "openai/text-embedding-3-small")
    RAG_EMBEDDING_DIMENSION: int = int(os.getenv("RAG_EMBEDDING_DIMENSION", "1536"))
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "6"))
    RAG_MIN_RELEVANCE: float = float(os.getenv("RAG_MIN_RELEVANCE", "0.25"))
    RAG_TEMPERATURE: float = float(os.getenv("RAG_TEMPERATURE", "0.2"))
    RAG_MAX_SHIPMENTS: int = int(os.getenv("RAG_MAX_SHIPMENTS", "300"))
    RAG_MAX_DEVICES: int = int(os.getenv("RAG_MAX_DEVICES", "300"))
    RAG_MAX_SENSOR_LOGS: int = int(os.getenv("RAG_MAX_SENSOR_LOGS", "500"))
    RAG_MAX_CUSTODY_CHECKPOINTS: int = int(os.getenv("RAG_MAX_CUSTODY_CHECKPOINTS", "500"))
    RAG_TOOL_MAX_STEPS: int = int(os.getenv("RAG_TOOL_MAX_STEPS", "5"))
    CHAT_MEMORY_MAX_TURNS: int = int(os.getenv("CHAT_MEMORY_MAX_TURNS", "8"))
    CHAT_MEMORY_TTL_MINUTES: int = int(os.getenv("CHAT_MEMORY_TTL_MINUTES", "240"))
    TEMPERATURE_THRESHOLD_C: float = float(os.getenv("TEMPERATURE_THRESHOLD_C", "8"))
    AGENTIC_VECTOR_COLLECTION: str = os.getenv("AGENTIC_VECTOR_COLLECTION", "trustseal_agentic_docs")
    AGENTIC_TOP_K: int = int(os.getenv("AGENTIC_TOP_K", "5"))
    AGENTIC_SIMILARITY_THRESHOLD: float = float(os.getenv("AGENTIC_SIMILARITY_THRESHOLD", "0.35"))
    AGENTIC_MMR_FETCH_K: int = int(os.getenv("AGENTIC_MMR_FETCH_K", "20"))
    AGENTIC_MMR_LAMBDA: float = float(os.getenv("AGENTIC_MMR_LAMBDA", "0.5"))
    AGENTIC_LLM_MODEL: str = os.getenv("AGENTIC_LLM_MODEL", os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"))
    AGENTIC_EMBEDDING_MODEL: str = os.getenv(
        "AGENTIC_EMBEDDING_MODEL",
        os.getenv("RAG_EMBEDDING_MODEL", "openai/text-embedding-3-small"),
    )
    AGENTIC_CHUNK_SIZE: int = int(os.getenv("AGENTIC_CHUNK_SIZE", "800"))
    AGENTIC_CHUNK_OVERLAP: int = int(os.getenv("AGENTIC_CHUNK_OVERLAP", "120"))
    AGENTIC_BATCH_SIZE: int = int(os.getenv("AGENTIC_BATCH_SIZE", "32"))
    AGENTIC_MAX_RESPONSE_TOKENS: int = int(os.getenv("AGENTIC_MAX_RESPONSE_TOKENS", "450"))
    AGENTIC_TEMPERATURE: float = float(os.getenv("AGENTIC_TEMPERATURE", "0.2"))
    AGENTIC_MAX_TOOL_STEPS: int = int(os.getenv("AGENTIC_MAX_TOOL_STEPS", "4"))
    AGENTIC_POOL_MIN_SIZE: int = int(os.getenv("AGENTIC_POOL_MIN_SIZE", "1"))
    AGENTIC_POOL_MAX_SIZE: int = int(os.getenv("AGENTIC_POOL_MAX_SIZE", "2"))
    AGENTIC_EAGER_STARTUP: bool = os.getenv("AGENTIC_EAGER_STARTUP", "false").lower() == "true"
    AGENTIC_SHORT_MEMORY_WINDOW: int = int(os.getenv("AGENTIC_SHORT_MEMORY_WINDOW", "6"))
    AGENTIC_SHORT_MEMORY_TTL_MINUTES: int = int(os.getenv("AGENTIC_SHORT_MEMORY_TTL_MINUTES", "240"))
    AGENTIC_LONG_MEMORY_TOP_K: int = int(os.getenv("AGENTIC_LONG_MEMORY_TOP_K", "4"))
    
    @property
    def DATABASE_URL(self) -> str:
        if self.DATABASE_URL_OVERRIDE:
            return self.DATABASE_URL_OVERRIDE
        if self.POSTGRES_SSLMODE == "require":
            return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}?sslmode=require"
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def CORS_ORIGINS(self) -> List[str]:
        # Browser Origin header never has a trailing slash. Normalize to avoid false CORS mismatches.
        raw_origins = [origin.strip().rstrip("/") for origin in self.BACKEND_CORS_ORIGINS.split(",")]
        return [origin for origin in raw_origins if origin]
    
    class Config:
        case_sensitive = True

settings = Settings()
