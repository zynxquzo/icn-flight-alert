# flight_alert/exceptions.py
"""
Custom Exceptions
커스텀 예외 클래스
"""


class NotFoundException(Exception):
    """리소스를 찾을 수 없을 때 발생하는 예외"""
    def __init__(self, message: str = "Resource not found"):
        self.message = message
        super().__init__(self.message)


class BadRequestException(Exception):
    """잘못된 요청일 때 발생하는 예외"""
    def __init__(self, message: str = "Bad request"):
        self.message = message
        super().__init__(self.message)


class APIException(Exception):
    """외부 API 호출 실패 시 발생하는 예외"""
    def __init__(self, message: str = "External API call failed"):
        self.message = message
        super().__init__(self.message)


class UnauthorizedException(Exception):
    """JWT 누락·만료·무효 등 인증 실패"""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)