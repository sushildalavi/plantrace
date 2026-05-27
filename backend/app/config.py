from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg://querylens:querylens@db:5432/querylens"
    MIN_MEAN_MS: float = 0.0
    ALLOW_EXPLAIN_ANALYZE: bool = False
    EXPLAIN_TIMEOUT_MS: int = 5000

    LLM_ENABLED: bool = False
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"

    CORS_ORIGINS: str = "http://localhost:3030"
    ENVIRONMENT: str = "local"

    KAFKA_ENABLED: bool = False
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_GROUP_ID: str = "querylens-control-plane"
    KAFKA_TOPIC_QUERY_TELEMETRY: str = "query-telemetry"
    KAFKA_TOPIC_COLLECTOR_HEARTBEAT: str = "collector-heartbeats"

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


settings = Settings()
