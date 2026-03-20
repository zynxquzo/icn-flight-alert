# flight_alert/repositories/user_repository.py
"""
User Repository
사용자 데이터 액세스 계층
"""

from sqlalchemy.orm import Session
from sqlalchemy import select
from flight_alert.models.user import User


class UserRepository:
    """사용자 Repository"""
    
    def save(self, db: Session, user: User) -> User:
        """사용자 저장"""
        db.add(user)
        db.flush()
        db.refresh(user)
        return user

    def find_by_email(self, db: Session, email: str) -> User | None:
        """이메일로 사용자 조회"""
        stmt = select(User).where(User.email == email)
        return db.scalar(stmt)

    def find_by_id(self, db: Session, user_id: int) -> User | None:
        """ID로 사용자 조회"""
        return db.get(User, user_id)


user_repository = UserRepository()