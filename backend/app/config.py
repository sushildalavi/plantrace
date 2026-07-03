from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg://plantrace:plantrace@db:5432/plantrace"
    SUPABASE_DATABASE_URL: str = ""
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    MIN_MEAN_MS: float = 0.0
    ALLOW_EXPLAIN_ANALYZE: bool = False
    EXPLAIN_TIMEOUT_MS: int = 5000

    LLM_ENABLED: bool = False
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-pro"

    AI_PROVIDER: str = "disabled"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    AI_MODEL: str = "qwen2.5-coder:7b"
    AI_FALLBACK_MODEL: str = "llama3.1:8b"
    AI_TIMEOUT_SECONDS: int = 20

    CORS_ORIGINS: str = "http://localhost:3030"
    ENVIRONMENT: str = "local"

    KAFKA_ENABLED: bool = False
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_GROUP_ID: str = "plantrace-control-plane"
    KAFKA_TOPIC_QUERY_TELEMETRY: str = "query-telemetry"
    KAFKA_TOPIC_COLLECTOR_HEARTBEAT: str = "collector-heartbeats"
    KAFKA_TOPIC_TELEMETRY_DLQ: str = "telemetry-dlq"
    KAFKA_CONSUMER_MAX_RETRIES: int = 3
    KAFKA_RETRY_BACKOFFS_MS: str = "100,500,2000"
    KAFKA_CONSUMER_MAX_RECORDS: int = 500
    KAFKA_CONSUMER_POLL_TIMEOUT_MS: int = 1000

    REGRESSION_LATENCY_RATIO_MEDIUM: float = 2.0
    REGRESSION_LATENCY_RATIO_HIGH: float = 5.0
    REGRESSION_ROW_ESTIMATE_RATIO: float = 10.0
    REGRESSION_TEMP_BLKS_DELTA: int = 1000
    REGRESSION_CALL_RATIO: float = 2.0
    REGRESSION_COST_RATIO: float = 2.0
    REGRESSION_HNSW_SEVERITY: str = "critical"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def effective_database_url(self) -> str:
        return self.SUPABASE_DATABASE_URL.strip() or self.DATABASE_URL


settings = Settings()
