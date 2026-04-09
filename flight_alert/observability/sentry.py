"""
Sentry 초기화 (DSN 설정 시에만 활성).
"""

from __future__ import annotations

import logging

from flight_alert.config import get_settings

logger = logging.getLogger(__name__)


def init_sentry() -> None:
    settings = get_settings()
    if not settings.sentry_dsn:
        logger.info("SENTRY_DSN 미설정 — Sentry 비활성")
        return

    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
            LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR,
            ),
        ],
    )
    logger.info("Sentry 초기화 완료 (environment=%s)", settings.sentry_environment)
