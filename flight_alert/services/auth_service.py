# flight_alert/services/auth_service.py
"""
Auth Service
인증 관련 비즈니스 로직
"""

import os
import logging
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from dotenv import load_dotenv

from flight_alert.repositories.user_repository import user_repository
from flight_alert.models.user import User
from flight_alert.schemas.user import UserCreate, UserLogin

load_dotenv()

logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "30"))


class AuthService:
    """인증 서비스"""
    
    def _hash_password(self, password: str) -> str:
        """비밀번호를 bcrypt로 해싱"""
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    
    def _verify_password(self, password: str, hashed: str) -> bool:
        """입력된 비밀번호와 해시된 비밀번호를 비교"""
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    
    def signup(self, db: Session, data: UserCreate) -> User:
        """회원가입"""
        # 1. 이메일 중복 검사
        existing_user = user_repository.find_by_email(db, data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="이미 등록된 이메일입니다.",
            )
        
        # 2. 비밀번호 해싱
        hashed_password = self._hash_password(data.password)
        
        # 3. 사용자 저장
        new_user = User(email=data.email, password=hashed_password)
        user_repository.save(db, new_user)
        db.commit()
        
        logger.info(f"회원가입 완료: {data.email}")
        return new_user
    
    def login(self, db: Session, data: UserLogin) -> str:
        """로그인"""
        # 1. 이메일로 사용자 조회
        user = user_repository.find_by_email(db, data.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="이메일 또는 비밀번호가 올바르지 않습니다.",
            )
        
        # 2. 비밀번호 검증
        if not self._verify_password(data.password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="이메일 또는 비밀번호가 올바르지 않습니다.",
            )
        
        # 3. JWT 토큰 생성
        access_token = self._create_access_token(user.user_id)
        logger.info(f"로그인 성공: {user.email}")
        
        return access_token
    
    def _create_access_token(self, user_id: int) -> str:
        """JWT 토큰 생성"""
        expire = datetime.now(timezone.utc) + timedelta(minutes=EXPIRE_MINUTES)
        payload = {
            "sub": str(user_id),
            "exp": expire,
        }
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    
    def get_current_user(self, db: Session, token: str) -> User:
        """토큰으로 현재 사용자 조회"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: int = int(payload.get("sub"))
            
            if user_id is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="유효하지 않은 토큰입니다.",
                )
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="토큰이 만료되었습니다.",
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="유효하지 않은 토큰입니다.",
            )
        
        user = user_repository.find_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="사용자를 찾을 수 없습니다.",
            )
        
        return user


auth_service = AuthService()