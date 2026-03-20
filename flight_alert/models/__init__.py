# flight_alert/models/__init__.py
"""
Models package
SQLAlchemy ORM 모델들을 정의합니다.
"""

from database import Base
from .flight import Flight
from .flight_status_log import FlightStatusLog
from .notification import Notification, NotificationType
from .user import User

__all__ = [
    "Base",
    "Flight",
    "FlightStatusLog", 
    "Notification",
    "NotificationType",
    "User",
]