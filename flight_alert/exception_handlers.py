# flight_alert/exception_handlers.py
"""
Exception Handlers
예외 처리 핸들러
"""

import logging
import os
import traceback

from fastapi import Request, status
from fastapi.responses import JSONResponse

from flight_alert.exceptions import (
    NotFoundException,
    BadRequestException,
    APIException,
    UnauthorizedException,
)

logger = logging.getLogger(__name__)


def register_exception_handlers(app):
    """FastAPI 앱에 예외 핸들러 등록"""
    
    @app.exception_handler(NotFoundException)
    async def not_found_exception_handler(request: Request, exc: NotFoundException):
        """404 Not Found 처리"""
        logger.warning(f"NotFoundException: {exc.message}")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "error": {
                    "code": "NOT_FOUND",
                    "message": exc.message
                }
            }
        )
    
    @app.exception_handler(BadRequestException)
    async def bad_request_exception_handler(request: Request, exc: BadRequestException):
        """400 Bad Request 처리"""
        logger.warning(f"BadRequestException: {exc.message}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": {
                    "code": "BAD_REQUEST",
                    "message": exc.message
                }
            }
        )
    
    @app.exception_handler(APIException)
    async def api_exception_handler(request: Request, exc: APIException):
        """502 Bad Gateway 처리 (외부 API 에러)"""
        logger.error(f"APIException: {exc.message}")
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "success": False,
                "error": {
                    "code": "EXTERNAL_API_ERROR",
                    "message": exc.message
                }
            }
        )

    @app.exception_handler(UnauthorizedException)
    async def unauthorized_exception_handler(request: Request, exc: UnauthorizedException):
        """401 Unauthorized (JWT 누락·만료·무효·로그아웃)"""
        logger.warning("UnauthorizedException: %s — %s", exc.code, exc.message)
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "success": False,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                },
            },
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """예상치 못한 에러 처리.

        @app.exception_handler(Exception)은 Starlette 내부에서 ServerErrorMiddleware에
        등록되므로 CORSMiddleware 바깥에서 실행됩니다. 따라서 CORS 헤더를 여기서 직접
        추가해야 브라우저 CORS 오류가 발생하지 않습니다.
        """
        logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
        content: dict = {
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
            }
        }
        if os.getenv("DEBUG", "").lower() in ("1", "true"):
            content["error"]["detail"] = traceback.format_exc()
        response = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=content,
        )
        origin = request.headers.get("origin")
        if origin:
            allowed_raw = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
            allowed = (
                [o.strip() for o in allowed_raw.split(",") if o.strip()]
                if allowed_raw
                else ["http://localhost:5173", "http://127.0.0.1:5173"]
            )
            if origin in allowed:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"
        return response