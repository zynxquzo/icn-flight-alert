# flight_alert/services/scheduler_service.py
"""
Scheduler Service
APScheduler를 사용한 주기적 비행편 갱신
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)


class FlightScheduler:
    """비행편 자동 갱신 스케줄러"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.is_running = False
    
    def refresh_active_flights(self):
        """활성화된 비행편 자동 갱신
        
        - is_active=True인 비행편만 조회
        - 비행일(flight_date)이 오늘부터 이틀 뒤(포함)까지인 편만 갱신
          (예: 오늘이 5월 2일이면 5/2·5/3·5/4 출발로 등록된 편)
        - 각 비행편마다 API 호출 및 변경 감지
        """
        from database import SessionLocal
        from flight_alert.services.flight_service import flight_service
        from flight_alert.repositories.flight_repository import flight_repository
        
        logger.info("========== 비행편 자동 갱신 시작 ==========")
        
        # DB 세션 생성
        db = SessionLocal()
        
        try:
            # 갱신 대상: flight_date ∈ [오늘, 오늘+2일] (3일치)
            today = date.today()
            target_start = today
            target_end = today + timedelta(days=2)
            
            # 활성 비행편 조회
            from sqlalchemy import and_
            from flight_alert.models.flight import Flight
            
            active_flights = db.query(Flight).filter(
                and_(
                    Flight.is_active == True,
                    Flight.flight_date >= target_start,
                    Flight.flight_date <= target_end
                )
            ).all()
            
            logger.info(f"갱신 대상 비행편: {len(active_flights)}건")
            
            # 각 비행편 갱신
            success_count = 0
            error_count = 0
            changes_count = 0
            
            for flight in active_flights:
                try:
                    result = flight_service.refresh_flight(db, flight.flight_pk)
                    success_count += 1
                    
                    if result['changes_detected']:
                        changes_count += 1
                        logger.info(
                            f"✅ 변경 감지: flight_pk={flight.flight_pk}, "
                            f"flight_id={flight.flight_id}, "
                            f"변경={len(result['changes'])}건"
                        )
                    
                except Exception as e:
                    error_count += 1
                    logger.error(
                        f"❌ 갱신 실패: flight_pk={flight.flight_pk}, "
                        f"flight_id={flight.flight_id}, error={e}"
                    )
            
            logger.info(
                f"========== 비행편 자동 갱신 완료 ==========\n"
                f"대상: {len(active_flights)}건, "
                f"성공: {success_count}건, "
                f"실패: {error_count}건, "
                f"변경 감지: {changes_count}건"
            )
            
        except Exception as e:
            logger.error(f"스케줄러 실행 중 에러: {e}")
        
        finally:
            db.close()
    
    def start(self, interval_minutes: int = 10):
        """스케줄러 시작
        
        Args:
            interval_minutes: 갱신 주기 (분 단위, 기본 10분)
        """
        if self.is_running:
            logger.warning("스케줄러가 이미 실행 중입니다")
            return
        
        # Job 추가
        self.scheduler.add_job(
            func=self.refresh_active_flights,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id='refresh_flights_job',
            name='비행편 자동 갱신',
            replace_existing=True,
        )
        
        # 스케줄러 시작
        self.scheduler.start()
        self.is_running = True
        
        logger.info(f"✅ 스케줄러 시작됨 (주기: {interval_minutes}분)")
    
    def stop(self):
        """스케줄러 중지"""
        if not self.is_running:
            logger.warning("스케줄러가 실행 중이 아닙니다")
            return
        
        self.scheduler.shutdown()
        self.is_running = False
        
        logger.info("⏹️ 스케줄러 중지됨")


# 싱글톤 인스턴스
flight_scheduler = FlightScheduler()