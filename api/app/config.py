from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(API_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    xai_api_key: str = ""
    grok_api_key: str = ""
    xai_base_url: str = "https://api.x.ai/v1"
    grok_model: str = "grok-4-latest"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    records_path: Path = API_DIR / "data" / "records.json"
    faiss_dir: Path = API_DIR / "faiss_index"
    max_content_chars: int = 6000
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def api_key(self) -> str:
        return self.xai_api_key or self.grok_api_key

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
