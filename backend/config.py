"""
config.py

Single source of truth for all runtime settings.
Change providers by editing .env — no code edits required.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    #  Provider selection 
    # sentence_transformer | ollama | hf_inference_embed
    embedding_provider: str = "sentence_transformer"
    # ollama | openai_compat | hf_inference
    llm_provider: str = "ollama"

    #  Sentence Transformers 
    st_model: str = "all-MiniLM-L6-v2"

    #  Ollama 
    ollama_base_url: str = "http://localhost:11434"
    ollama_llm_model: str = "llama3.2"
    ollama_embed_model: str = "nomic-embed-text"

    #  OpenAI-compatible endpoint 
    openai_compat_base_url: str = "http://localhost:1234/v1"
    openai_compat_api_key: str = "not-needed"
    openai_compat_model: str = "local-model"

    #  HuggingFace Inference API 
    hf_token: str = ""
    hf_llm_model: str = "HuggingFaceH4/zephyr-7b-beta"
    hf_embed_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    #  Connectors 
    slack_bot_token: str = ""
    github_token: str = ""
    # Empty = use bundled backend/data/synthetic_dataset.json
    dataset_path: str = ""

    #  Pipeline tuning 
    ingest_days_back: int = 30
    hdbscan_min_cluster_size: int = 2
    staleness_halflife_days: float = 7.0
    max_threads_per_brief: int = 8

    #  App 
    database_url: str = "sqlite+aiosqlite:///./chp.db"
    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()
