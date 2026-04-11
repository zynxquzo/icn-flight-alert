# flight_alert/models/__init__.py
"""
Models package
SQLAlchemy ORM 모델들을 정의합니다.
"""

from database import Base
from .airport_document import AirportDocument
from .flight import Flight
from .flight_status_log import FlightStatusLog
from .notification import Notification, NotificationType
from .user import User

__all__ = [
    "Base",
    "AirportDocument",
    "Flight",
    "FlightStatusLog",
    "Notification",
    "NotificationType",
    "User",
]