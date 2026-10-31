import os
from typing import Optional
from pydantic import BaseModel, Field

class AutoHealConfig(BaseModel):
    api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("AUTOHEAL_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("GEMINI_API_KEY")
    )
    model: str = Field(
        default_factory=lambda: os.getenv("AUTOHEAL_MODEL", "gpt-4o")
    )
    provider: str = Field(
        default_factory=lambda: os.getenv("AUTOHEAL_PROVIDER", "openai")
    )
    github_token: Optional[str] = Field(
        default_factory=lambda: os.getenv("AUTOHEAL_GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")
    )
    test_command: str = Field(
        default_factory=lambda: os.getenv("AUTOHEAL_TEST_CMD", "pytest")
    )
    max_rounds: int = Field(
        default_factory=lambda: int(os.getenv("AUTOHEAL_MAX_ROUNDS", "3"))
    )
    max_budget_usd: Optional[float] = Field(
        default_factory=lambda: float(os.getenv("AUTOHEAL_MAX_BUDGET_USD")) if os.getenv("AUTOHEAL_MAX_BUDGET_USD") else None
    )
    create_pr: bool = Field(
        default_factory=lambda: os.getenv("AUTOHEAL_CREATE_PR", "true").lower() in ("true", "1", "yes")
    )
    repo_path: str = Field(
        default_factory=lambda: os.getenv("GITHUB_WORKSPACE", os.getcwd())
    )
