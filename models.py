from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime
import os

Base = declarative_base()

class MarketStatus(Base):
    __tablename__ = 'market_status'
    id = Column(Integer, primary_key=True)
    symbol = Column(String)
    market_status_long = Column(String)
    market_status_short = Column(String)

class BalanceData(Base):
    __tablename__ = 'balance_data'
    id = Column(Integer, primary_key=True)
    wallet = Column(Float)
    total = Column(Float)
    free = Column(Float)
    used = Column(Float)
    pnl = Column(Float)

class PositionData(Base):
    __tablename__ = 'position_data'
    id = Column(Integer, primary_key=True)
    symbol = Column(String)
    avg_price = Column(Float)
    position_amount = Column(Float)
    leverage = Column(Float)
    unrealized_profit = Column(Float)
    breakeven_price = Column(Float)
    market_status = Column(String)  

    def __repr__(self):
        return (f"<PositionData(symbol={self.symbol}, avg_price={self.avg_price}, "
                f"position_amount={self.position_amount}, leverage={self.leverage}, "
                f"unrealized_profit={self.unrealized_profit}, breakeven_price={self.breakeven_price}, "
                f"market_status={self.market_status})>")
    
class CoinData(Base):
    """
    CoinData 테이블은 각 코인의 캔들 차트 데이터를 저장합니다.
    단일 테이블에 symbol과 interval 컬럼을 포함하여 다양한 시간 간격 데이터를 관리합니다.
    """
    __tablename__ = 'coin_data'
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)      # 예: 'BTCUSDT'
    interval = Column(String, index=True)      # 예: '1m', '15m', ...
    open_time = Column(DateTime, default=datetime.datetime.utcnow)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)

# 데이터베이스 위치 및 연결 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # 예: /my_bot
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'my_bot.db')}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)

def initialize_database():
    # Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)  # 테이블 생성만 수행
    return engine

# 모듈 로드 시 초기화
initialize_database()
