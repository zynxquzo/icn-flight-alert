# flight_alert/schemas/common.py
"""
Common Schemas
공통 응답 스키마
"""

from pydantic import BaseModel
from typing import Any, Generic, TypeVar

T = TypeVar('T')


class SuccessResponse(BaseModel, Generic[T]):
    """성공 응답"""
    success: bool = True
    data: T
    message: str


class ErrorResponse(BaseModel):
    """에러 응답"""
    success: bool = False
    error: dict[str, Any]


class PaginationResponse(BaseModel, Generic[T]):
    """페이지네이션 응답"""
    items: list[T]
    total: int
    page: int
    limit: int
    total_pages: int