"""Global Configuration Settings."""

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "AirCreator API"
    app_version: str = "0.1.0"
    debug: bool = True
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


settings = Settings()
