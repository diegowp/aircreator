"""Global Configuration Settings and Path Resolvers."""

from pathlib import Path
from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "AirCreator API"
    app_version: str = "0.1.0"
    debug: bool = True
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
    ]


settings = Settings()


def get_project_root() -> Path:
    """Return the absolute path to the AirCreator project root."""
    return Path(__file__).resolve().parents[3]


def resolve_blueprint_path(path_str: str | None) -> Path | None:
    """
    Robustly resolve blueprint path across multiple possible locations:
    - Absolute or current working directory
    - Project root / path_str
    - Project root / docs / filename
    - Project root / output / filename
    - Project root / uploads / filename
    """
    if not path_str:
        path_str = "docs/blueprint.jpg"

    p = Path(path_str)
    if p.is_file():
        return p

    if (Path.cwd() / path_str).is_file():
        return Path.cwd() / path_str

    root = get_project_root()
    candidates = [
        root / path_str,
        root / "docs" / p.name,
        root / "output" / p.name,
        root / "uploads" / p.name,
        Path.cwd().parent / path_str,
        Path.cwd() / "docs" / p.name,
    ]

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    return None
