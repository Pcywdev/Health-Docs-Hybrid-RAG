"""Frontend settings, loaded from the environment or .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class UISettings(BaseSettings):
    """Where the UI finds the API, and how long it waits for an answer."""

    # .env also holds the API's keys; ignore them instead of failing on extras
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_url: str = "http://127.0.0.1:8000"
    # Retrieval + rerank + generation usually takes a few seconds; allow slow upstreams
    request_timeout_s: float = 60.0


ui_settings = UISettings()
