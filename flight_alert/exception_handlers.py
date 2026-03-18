# flight_alert/exception_handlers.py
"""
Exception Handlers
예외 처리 핸들러
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from flight_alert.exceptions import NotFoundException, BadRequestException, APIException
import logging

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
    
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        """ValueError를 404로 처리"""
        logger.warning(f"ValueError: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "error": {
                    "code": "NOT_FOUND",
                    "message": str(exc)
                }
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """예상치 못한 에러 처리"""
        logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred"
                }
            }
        )