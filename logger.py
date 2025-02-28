import logging
from logging.handlers import RotatingFileHandler
import telegram
import asyncio
import os
from collections import deque
from typing import Dict, Any
from pathlib import Path
from datetime import datetime, timedelta
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
from config import TRADE_LOG, BALANCE_LOG, PROGRAM_LOG, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, LOG_DIR
import threading
import queue  # queue 모듈 추가

class Logger:
    """
    향상된 로깅 시스템의 메인 클래스
    싱글톤 패턴을 사용하여 하나의 인스턴스만 유지
    """
    _instance = None
    
    def __new__(cls):
        """싱글톤 패턴 구현: 클래스의 인스턴스가 하나만 생성되도록 보장"""
        if not cls._instance:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance.__initialized = False
        return cls._instance

    def __init__(self):
        """
        Logger 클래스 초기화
        이미 초기화된 경우 중복 초기화 방지
        """
        if self.__initialized:
            return
            
        self.__initialized = True
        self._lock = threading.Lock()  # 스레드 안전성을 위한 락
        self.stop_event = threading.Event()
        
        # 로그 디렉토리 설정
        self.log_dir = Path(LOG_DIR)
        self.archive_dir = self.log_dir / "archive"
 
        self.memory_logs = {
            'trade': deque(maxlen=100),
            'balance': deque(maxlen=100),
            'system': deque(maxlen=100)
        } 
        # 로거 설정
        self._setup_loggers()
        
        # Telegram 봇 및 비동기 작업 설정
        self.bot = telegram.Bot(TELEGRAM_TOKEN)
        self.telegram_queue = queue.Queue()  # 비동기 작업 큐
        self.loop = asyncio.new_event_loop()  # 전용 이벤트 루프
        self.telegram_thread = threading.Thread(target=self._run_telegram_loop, daemon=True)
        self.telegram_thread.name = "TelegramAlertThread"
        self.telegram_thread.start()

        # 텔레그램 봇 설정
        # self.bot = telegram.Bot(TELEGRAM_TOKEN)
    
    def _run_telegram_loop(self):
        asyncio.set_event_loop(self.loop)
        while not self.stop_event.is_set():
            # self.info("텔레그램 루프 실행 중")  # 디버그 로그
            try:
                message = self.telegram_queue.get(timeout=1.0)
                self.info(f"텔레그램 메시지 처리 중: {message}")
                asyncio.run_coroutine_threadsafe(self.send_telegram_alert_async(message), self.loop)
                self.telegram_queue.task_done()
            except queue.Empty:
                # self.info("텔레그램 큐가 비어 있음, 계속 진행")
                continue
            except Exception as e:
                self.error(f"텔레그램 루프 오류: {str(e)}")

    def _run_telegram_loop1(self):
        """Telegram 전송을 위한 전용 이벤트 루프 실행"""
        asyncio.set_event_loop(self.loop)
        while not self.stop_event.is_set():
            try:
                message = self.telegram_queue.get(timeout=1.0)  # 큐에서 메시지 대기
                asyncio.run_coroutine_threadsafe(self.send_telegram_alert_async(message), self.loop)
                self.telegram_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Telegram loop error: {str(e)}")
        self.loop.close()

    def _setup_loggers(self):
        """로거 설정"""
        # 기본 포맷터
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        formatter_1 = logging.Formatter(
            '%(asctime)s %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 각 로거 생성
        self.trade_logger = self._create_logger('trade', 'trade_log.txt', formatter_1)
        self.balance_logger = self._create_logger('balance', 'balance_log.txt', formatter_1)
        self.program_logger = self._create_logger('system', 'program_log.txt', formatter)


    def _create_logger(self, name: str, filename: str, formatter: logging.Formatter) -> logging.Logger:
        """개별 로거 생성"""
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        
        # 기존 핸들러 제거
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        try:
            # 파일 핸들러
            file_handler = RotatingFileHandler(
                self.log_dir / filename,
                maxBytes=10*1024*1024,
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
        except Exception as e:
            self.error(f"{name} 파일 핸들러 생성 실패: {str(e)}")
            raise

        # 메모리 스트림 핸들러
        class MemoryStreamHandler(logging.StreamHandler):
            def __init__(self, memory_logs: Dict[str, deque], category: str):
                super().__init__()
                self.memory_logs = memory_logs
                self.category = category

            def emit(self, record):
                try:
                    # 콘솔 출력
                    super().emit(record)
                    
                    # 메모리에 저장
                    log_entry = {
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'level': record.levelno,
                        'message': record.getMessage(),
                        'category': self.category
                    }
                    self.memory_logs[self.category].append(log_entry)
                except Exception as e:
                    print(f"Memory logging failed: {str(e)}")

        # 메모리 스트림 핸들러 추가
        memory_handler = MemoryStreamHandler(self.memory_logs, name)
        memory_handler.setFormatter(formatter)
        
        # 핸들러 추가
        logger.addHandler(file_handler)
        logger.addHandler(memory_handler)
        
        return logger

    def stop(self):
        self.stop_event.set()
        self.telegram_thread.join(timeout=2)
        self.info("로거 종료")

    def log(self, level: int, category: str, message: str, telegram: bool = None):
        """
        통합 로깅 메서드
        
        Args:
            level: 로그 레벨 (LogLevel 클래스의 상수 사용)
            category: 로그 카테고리 (LogCategory 클래스의 상수 사용)
            message: 로그 메시지
            telegram: 텔레그램 알림 강제 발송 여부
        """
        with self._lock:  # 스레드 안전성 보장
            try:
                # 카테고리 포함하여 메시지 포맷팅
                formatted_message = f"[{category}] {message}"
                
                # 적절한 로거 선택 및 로깅
                if category == 'TRADE':
                    self.trade_logger.log(level, formatted_message)
                elif category == 'BALANCE':
                    self.balance_logger.log(level, formatted_message)
                else:
                    self.program_logger.log(level, formatted_message)

            except Exception as e:
                print(f"Logging failed: {str(e)}")

    # 편의성을 위한 래퍼 메서드들
    def trade1(self, message: str):
        self.log(logging.INFO, 'TRADE', message)

    def trade(self, message: str):
        self.log(logging.INFO, 'TRADE', message)
        self.info(f"텔레그램 스레드 상태: {self.telegram_thread.is_alive()}")

    def balance(self, message: str):
        self.log(logging.INFO, 'BALANCE', message)

    def system(self, message: str):
        self.log(logging.INFO, 'SYSTEM', message)

    def error(self, message: str):
        self.log(logging.ERROR, 'SYSTEM', message)

    def warning(self, message: str):
        self.log(logging.WARNING, 'SYSTEM', message)

    def info(self, message: str):
        """시스템 관련 로그"""
        self.log(logging.INFO, 'SYSTEM', message)


    async def send_telegram_alert_async(self, message: str):
        """
        비동기 텔레그램 알림 발송
        """
        try:
            # await self.bot.send_message(
            #     chat_id=TELEGRAM_CHAT_ID,
            #     text=message
            #     # parse_mode='HTML'
            # )

            await asyncio.wait_for(
                self.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            self.error("텔레그램 전송 타임아웃")
        except Exception as e:
            self.error(f"텔레그램 알림 실패: {str(e)}")

    def send_telegram_alert_sync(self, message: str):
        """큐를 통해 비동기 작업을 안전하게 처리"""
        if not self.stop_event.is_set():
            self.telegram_queue.put(message)

    def send_telegram_alert_sync1(self, message: str):
        """
        동기 방식의 텔레그램 알림 발송
        """
        try:
            # 이미 실행 중인 이벤트 루프가 있는 경우를 대비한 처리
            try:
                asyncio.run(self.send_telegram_alert_async(message))
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.send_telegram_alert_async(message))
                loop.close()
        except Exception as e:
            print(f"Telegram alert failed: {str(e)}")


# 로거 인스턴스 생성
logger = Logger()

