# flight_alert/repositories/user_repository.py
"""
User Repository
사용자 데이터 액세스 계층
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flight_alert.models.user import User


class UserRepository:
    """사용자 Repository"""

    async def save(self, db: AsyncSession, user: User) -> User:
        """사용자 저장"""
        db.add(user)
        await db.flush()
        await db.refresh(user)
        return user

    async def find_by_email(self, db: AsyncSession, email: str) -> User | None:
        """이메일로 사용자 조회"""
        stmt = select(User).where(User.email == email)
        return await db.scalar(stmt)

    async def find_by_id(self, db: AsyncSession, user_id: int) -> User | None:
        """ID로 사용자 조회"""
        return await db.get(User, user_id)


user_repository = UserRepository()
