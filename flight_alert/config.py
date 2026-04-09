"""
애플리케이션 공통 설정 (환경 변수).
"""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    return float(raw)


@lru_cache
def get_settings() -> "Settings":
    return Settings()


class Settings:
    """환경 변수 기반 설정 (싱글톤)."""

    # Redis (JWT 블랙리스트·스케줄러 리더 락)
    redis_url: str | None = os.getenv("REDIS_URL", "").strip() or None

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "30"))
    jwt_refresh_expire_days: int = int(os.getenv("JWT_REFRESH_EXPIRE_DAYS", "14"))

    # 스케줄러
    enable_scheduler: bool = env_bool("ENABLE_SCHEDULER", default=True)
    scheduler_interval_minutes: int = int(os.getenv("SCHEDULER_INTERVAL_MINUTES", "10"))
    scheduler_leader_lock: bool = env_bool("SCHEDULER_LEADER_LOCK", default=True)

    # 관측
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_json: bool = env_bool("LOG_JSON", default=False)
    sentry_dsn: str | None = os.getenv("SENTRY_DSN", "").strip() or None
    sentry_environment: str = os.getenv("SENTRY_ENVIRONMENT", "development")
    sentry_traces_sample_rate: float = env_float("SENTRY_TRACES_SAMPLE_RATE", 0.1)

    # 기타 (auth_service 호환)
    frontend_public_url: str = os.getenv(
        "FRONTEND_PUBLIC_URL", "http://localhost:5173"
    ).rstrip("/")
    require_email_verification: bool = env_bool("REQUIRE_EMAIL_VERIFICATION", False)

    def __init__(self) -> None:
        secret = os.getenv("JWT_SECRET_KEY")
        if not secret or not str(secret).strip():
            raise ValueError("JWT_SECRET_KEY 환경 변수가 설정되지 않았습니다")
        self.jwt_secret_key = str(secret).strip()

    @property
    def redis_enabled(self) -> bool:
        return bool(self.redis_url)
