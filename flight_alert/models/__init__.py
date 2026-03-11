# flight_alert/models/__init__.py
"""
Models package
SQLAlchemy ORM 모델들을 정의합니다.
"""

from .flight import Flight
from .flight_status_log import FlightStatusLog
from .notification import Notification, NotificationType
from database import Base

__all__ = [
    "Flight",
    "FlightStatusLog", 
    "Notification",
    "NotificationType",
    "Base"
]