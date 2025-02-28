import time
import os
import json
import threading
import hmac
import hashlib
import requests
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager

import pandas as pd
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 내부 모듈 및 ORM 관련 설정
from binance.client import Client
from config import API_KEY, SECRET_KEY, COIN_LIST, DATA_DIR, BASE_URL, TARGET_LEVERAGE
from models import MarketStatus, BalanceData, PositionData, CoinData, Session
from logger import logger  # 내부 logger 사용

import websocket
import pandas_ta as ta
import numpy as np
import sys

# logger = logger.getLogger(__name__)
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class DataHandler:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(DataHandler, cls).__new__(cls)
                    cls._instance.__initialized = False
        return cls._instance
    
    def __init__(self):
        if self.__initialized:
            return
        self.__initialized = True
        self.client = Client(API_KEY, SECRET_KEY)
        self.lock = threading.Lock()  # lock 속성 추가
        self.coin_data = {symbol: {} for symbol in COIN_LIST}
        self.orderbook_data = {symbol: None for symbol in COIN_LIST}  # orderbook_data 추가
        self.position_data = {symbol: {} for symbol in COIN_LIST}
        self.balance_data = {"wallet": 0.0, "total": 0.0, "free": 0, "used": 0.0, "PNL": 0.0}
        self.tick_size = {symbol: {} for symbol in COIN_LIST}
        logger.system(f"DataHandler Class 시작")
        self.session = self._create_session()
        from models import initialize_database
        initialize_database()
        self.start_account_info_thread()

    def _create_session(self):
        session = requests.Session()
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        session.mount('https://', HTTPAdapter(max_retries=retries))
        return session

    @contextmanager
    def session_scope(self):
        """
        데이터베이스 세션을 생성하고, 함수 종료 후 commit/rollback 및 session close를 자동으로 처리하는 context manager.
        """
        session = Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error("DB 세션 롤백 발생")
            raise e
        finally:
            session.close()

    def initialize_data(self):
        """초기 데이터 설정"""
        try:
            # 잔고 데이터 초기화
            self.balance_data_update()
            # logger.balance("잔고 데이터 초기화 완료")

            # 코인별 데이터 초기화
            for symbol in COIN_LIST:
                try:
                    self.coin_data[symbol] = {
                        '1m': self.load_historical_data(symbol, '1m'),
                        '15m': self.load_historical_data(symbol, '15m')
                    }
                    self.position_data_update(symbol)
                    self.set_leverage(symbol)
                    # logger.trade(f"{symbol} 초기 데이터 로드 완료")
                except Exception as e:
                    logger.error(f"{symbol} 데이터 초기화 실패: {str(e)}")

            # logger.system("전체 데이터 초기화 완료")
            
        except Exception as e:
            logger.error(f"데이터 초기화 중 오류 발생: {str(e)}")
            raise    


    def get_tick_size(self):
        info = self.client.futures_exchange_info()
        for s in info['symbols']:
            if s['symbol'] in COIN_LIST:
                for f in s['filters']:
                    if f['filterType'] == 'PRICE_FILTER':
                        self.tick_size[s['symbol']] = float(f['tickSize'])
        print('tick_size',self.tick_size)                
        return self.tick_size
            
    def set_leverage(self, symbol):
        """레버리지 설정 (기존 로직 유지)"""
        try:
            self.client.futures_change_leverage(
                symbol=symbol, 
                leverage=TARGET_LEVERAGE
            )
        except Exception as e:
            logger.error(f"{symbol} 레버리지 설정 실패: {e}")

    def write_balance(self,binance_balance):
        with open("my_bot/binance_balance.txt", "a") as fp :
            fp.write(binance_balance)
            fp.write('\n')

    def get_account_info(self):
        url = f"{BASE_URL}/fapi/v2/account"

        # 타임스탬프와 서명 생성
        timestamp = int(time.time() * 1000)
        query_string = f"timestamp={timestamp}"
        signature = hmac.new(
            SECRET_KEY.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # 요청 헤더 설정
        headers = {
            "X-MBX-APIKEY": API_KEY
        }
        try:
            # 요청 보내기
            # response = requests.get(url, headers=headers, params={"timestamp": timestamp, "signature": signature})
            response = self.session.get(url, headers=headers, params={"timestamp": timestamp, "signature": signature}, timeout=10)

            # 결과 반환
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": response.status_code, "message": response.text}
        except requests.exceptions.RequestException as e:
            return {"error": "ConnectionError", "message": str(e)}     
           
    def account_status(self):
        while True:
            try:
                balance = self.get_account_info()
                positions = balance["positions"]

                total_wallet_balance = round(float(balance['totalWalletBalance']),4) # total wallet balance, only for USDT asset
                total_unrealized_profit = round(float(balance['totalUnrealizedProfit']),4)
                usdt_free = round(float(balance['availableBalance']),4) # usdt_free
                usdt_used = round(float(balance['totalInitialMargin']),4) # usdt_used
                usdt_total = round(float(balance['totalMarginBalance']),4) # usdt_total

                self.balance_data.update({
                    'wallet': total_wallet_balance,
                    'total': usdt_total,
                    'free': usdt_free,
                    'used': usdt_used,
                    'PNL': total_unrealized_profit
                })

                for symbol in COIN_LIST:
                    for position in positions:
                        if position["symbol"] == symbol:
                            avg_price = round(float(position['entryPrice']),4)
                            position_amount = round(float(position['positionAmt']),4)
                            leverage = round(float(position['leverage']),4)
                            unrealized_profit = round(float(position['unrealizedProfit']),4)
                            breakeven_price = round(float(position['breakEvenPrice']),4)

                            self.position_data[symbol].update({ 
                                'avg_price': avg_price,
                                'position_amount': position_amount,
                                'leverage': leverage,
                                'unrealizedProfit': unrealized_profit,
                                'breakeven_price': breakeven_price
                            })

            except websocket.WebSocketException as e:
                logger.error("Error:", e)
                break

    def balance_data_update(self,event_reason=None):
        nowtime = datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S')
        balance = self.get_account_info()
        # print(balance)
        total_wallet_balance = round(float(balance['totalWalletBalance']),4) # total wallet balance, only for USDT asset
        total_unrealized_profit = round(float(balance['totalUnrealizedProfit']),4)
        usdt_free = round(float(balance['availableBalance']),4) # usdt_free
        usdt_used = round(float(balance['totalInitialMargin']),4) # usdt_used
        usdt_total = round(float(balance['totalMarginBalance']),4) # usdt_total

        self.balance_data.update({
            'wallet': total_wallet_balance,
            'total': usdt_total,
            'free': usdt_free,
            'used': usdt_used,
            'PNL': total_unrealized_profit
        })

        binance_balance = (
                        # f"{nowtime}\t"
                        f"wallet: {total_wallet_balance}\t"
                        f"total: {usdt_total}\t"
                        f"free: {usdt_free}\t"
                        f"used: {usdt_used}\t"
                        f"PNL: {total_unrealized_profit}"
                        )
        # event_reason이 전달된 경우, 추가
        if event_reason:
            binance_balance += f"\t{event_reason}"

        logger.balance(binance_balance)
        # print(binance_balance)
        self.write_balance(binance_balance) # write balance to file
        return self.balance_data
    
    def position_data_update(self,symbol):
        url = f"{BASE_URL}/fapi/v2/positionRisk"

        # 타임스탬프와 서명 생성
        timestamp = int(time.time() * 1000)
        query_string = f"symbol={symbol}&timestamp={timestamp}"
        signature = hmac.new(
            SECRET_KEY.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # 요청 헤더 설정
        headers = {
            "X-MBX-APIKEY": API_KEY
        }
        try:
            # 요청 보내기
            response = requests.get(url, headers=headers, params={"symbol": symbol, "timestamp": timestamp, "signature": signature})
        except requests.exceptions.RequestException as e:
            return {"error": "ConnectionError", "message": str(e)}     

        # 결과 반환
        if response.status_code == 200:
            data = response.json()
            if data:
                self.position_data[symbol].update({
                    "avg_price": round(float(data[0]['entryPrice']),4),
                    "position_amount": round(float(data[0]['positionAmt']),4),
                    "leverage": int(data[0]['leverage']),
                    "unrealizedProfit": round(float(data[0]['unRealizedProfit']),4),
                    "breakeven_price": round(float(data[0]['breakEvenPrice']),4),
                    "market_status" : "unknown "
                })
                logger.info(f"{symbol}, {self.position_data[symbol]}") # print(symbol,self.position_data[symbol])
                return self.position_data[symbol]
        else:
            logger.error(f"Error fetching leverage for {symbol}: {response.text}")

    def save_orderbook_data(self, symbol):
        """오더북 데이터 저장"""
        path = os.path.join(DATA_DIR, f"orderbook_{symbol}.csv")
        df = pd.DataFrame(self.orderbook_data[symbol])
        df.to_csv(path, index=False)


    def load_historical_data(self, symbol, interval, limit=260, save_to_file=True):
        """
        Binance API를 통해 과거 데이터를 로드하고, 필요시 파일로 저장합니다.
        
        :param symbol: 코인 심볼 (예: 'BTCUSDT')
        :param interval: 데이터 간격 (예: '1m', '1h')
        :param limit: 가져올 데이터 개수
        :param save_to_file: 데이터를 파일로 저장할지 여부 (기본값: True)
        :return: pandas DataFrame
        """
        try:
            # Binance API를 통해 데이터 가져오기
            raw_data = self.client.futures_klines(
                symbol=symbol, 
                interval=interval, 
                limit=limit
            )
            
            # 데이터프레임으로 변환
            df = pd.DataFrame(raw_data, columns=[
                'Open time', 'Open', 'High', 'Low', 'Close', 'Volume',
                'Close time', 'Quote asset volume', 'Number of trades',
                'Taker buy base asset volume', 'Taker buy quote asset volume', 'Ignore'
            ])
            
            # 필요한 컬럼만 선택 및 데이터 타입 변환
            df = df[['Open time', 'Open', 'High', 'Low', 'Close', 'Volume']]
            df['Open time'] = pd.to_datetime(df['Open time'], unit='ms') + pd.Timedelta(hours=9)
            df['Open'] = df['Open'].astype(float)
            df['High'] = df['High'].astype(float)
            df['Low'] = df['Low'].astype(float)
            df['Close'] = df['Close'].astype(float)
            df['Volume'] = df['Volume'].astype(float)

            # self.add_indicators(df)  # 지표 추가
            # 파일로 저장 (옵션)
            if save_to_file:
                file_path = os.path.join(DATA_DIR, f"klines_{symbol}_{interval}.csv")
                df.to_csv(file_path, index=False, sep='\t')
                # logger.info(f"📁 데이터 저장 완료: {file_path}")

            self.save_to_coin_data_db(symbol, interval, df)    
            
            return df
        
        except Exception as e:
            logger.error(f"❌ 데이터 로드 실패: {e}")
            return pd.DataFrame()  # 빈 데이터프레임 반환


    def start_account_info_thread(self):
        """계정 정보를 2초마다 업데이트하는 스레드 시작"""
        def run():
            while True:
                account_info = self.get_account_info()
                if "error" not in account_info:
                    self.update_account_data(account_info)
                time.sleep(10)

        thread = threading.Thread(target=run)
        thread.daemon = True
        thread.name = "AccountInfoUpdateThread"
        thread.start()

    def update_account_data(self, account_info):
        """계정 정보 데이터를 업데이트"""
        balances = account_info["assets"]
        positions = account_info["positions"]

        for balance in balances:
            if balance["asset"] == "USDT":
                total_wallet_balance = round(float(balance["walletBalance"]),4)
                total_unrealized_profit = round(float(balance["unrealizedProfit"]),4)
                usdt_free = round(float(balance["availableBalance"]),4)
                usdt_used = round(float(balance["initialMargin"]),4)
                usdt_total = round(float(balance["marginBalance"]),4)

                balance_data = {
                    'wallet': total_wallet_balance,
                    'total': usdt_total,
                    'free': usdt_free,
                    'used': usdt_used,
                    'PNL': total_unrealized_profit
                }

                self.balance_data.update(balance_data)
                self.save_db_balance_data(balance_data)
                # self.data_handler.balance_data.update({
                #     'wallet': total_wallet_balance,
                #     'total': usdt_total,
                #     'free': usdt_free,
                #     'used': usdt_used,
                #     'PNL': total_unrealized_profit
                # })

        for symbol in COIN_LIST:
            for position in positions:
                if position["symbol"] == symbol:
                    symbol = position["symbol"]
                    position_amount = round(float(position["positionAmt"]),4)
                    avg_price = round(float(position["entryPrice"]),4)
                    leverage = round(float(position["leverage"]),4)
                    unrealized_profit = round(float(position["unrealizedProfit"]),4)
                    breakeven_price = round(float(position["breakEvenPrice"]),4)

                    self.position_data[symbol].update({ 
                        'avg_price': avg_price,
                        'position_amount': position_amount,
                        'leverage': leverage,
                        'unrealizedProfit': unrealized_profit,
                        'breakeven_price': breakeven_price
                    })
                    position_data = {
                        'symbol': symbol,
                        'avg_price': avg_price,
                        'position_amount': position_amount,
                        'leverage': leverage,
                        'unrealizedProfit': unrealized_profit,
                        'breakeven_price': breakeven_price
                        # 'market_status': position.get('market_status', 'Unknown')
                    }
                    self.save_db_position_data(position_data)

    def save_db_market_status(self, market_status):
        with self.session_scope() as session:
            market = session.query(MarketStatus).filter_by(symbol=market_status['symbol']).first()
            if market:
                market.market_status_long = market_status['market_status_long']
                market.market_status_short = market_status['market_status_short']
            else:
                market = MarketStatus(
                    symbol=market_status['symbol'],
                    market_status_long=market_status['market_status_long'],
                    market_status_short=market_status['market_status_short']
                )
                session.add(market)
            # logger.info(f"Market status saved for {market_status['symbol']}")

    def save_to_coin_data_db(self, symbol, interval, df):
        """
        pandas DataFrame 형식의 캔들 데이터를 CoinData DB에 저장합니다.
        save_db_balance_data 스타일을 반영하여 기존 데이터를 삭제 후 새로 삽입.
        
        :param symbol: 코인 심볼 (예: 'BTCUSDT')
        :param interval: 데이터 간격 (예: '1m', '15m')
        :param df: 캔들 데이터가 포함된 pandas DataFrame
        """
        with self.session_scope() as session:
            try:
                # 해당 symbol과 interval의 기존 데이터 삭제
                session.query(CoinData).filter_by(symbol=symbol, interval=interval).delete()

                # 새 데이터 삽입
                for _, row in df.iterrows():
                    candle = CoinData(
                        symbol=symbol,
                        interval=interval,
                        open_time=row['Open time'],
                        open=row['Open'],
                        high=row['High'],
                        low=row['Low'],
                        close=row['Close'],
                        volume=row['Volume']
                    )
                    session.add(candle)

                session.commit()
                logger.info(f"{symbol} {interval} 캔들 데이터가 CoinData DB에 저장되었습니다")
            except Exception as e:
                session.rollback()
                logger.error(f"{symbol} {interval} CoinData DB 저장 중 오류 발생: {str(e)}")
                raise

    def _update_incomplete_candle_in_db(self, symbol, timeframe, candle):
        """
        미완료된 캔들 데이터를 CoinData DB에서 업데이트하거나 추가합니다.
        
        :param symbol: 코인 심볼 (예: 'BTCUSDT')
        :param timeframe: 캔들 시간 간격 (예: '1m', '15m')
        :param candle: 캔들 데이터 딕셔너리
        """
        with self.session_scope() as session:
            try:
                # 마지막 캔들 찾기 (가장 최근 open_time 기준)
                existing = session.query(CoinData).filter_by(
                    symbol=symbol,
                    interval=timeframe
                ).order_by(CoinData.open_time.desc()).first()

                if existing and existing.open_time == candle['Open time']:
                    # 기존 캔들 업데이트
                    existing.open = candle['Open']
                    existing.high = candle['High']
                    existing.low = candle['Low']
                    existing.close = candle['Close']
                    existing.volume = candle['Volume']
                else:
                    # 새로운 미완료 캔들 추가
                    new_candle = CoinData(
                        symbol=symbol,
                        interval=timeframe,
                        open_time=candle['Open time'],
                        open=candle['Open'],
                        high=candle['High'],
                        low=candle['Low'],
                        close=candle['Close'],
                        volume=candle['Volume']
                    )
                    session.add(new_candle)
                
                session.commit()
                # logger.info(f"{symbol} {timeframe} 미완료 캔들 데이터가 CoinData DB에 업데이트됨")
            except Exception as e:
                session.rollback()
                logger.error(f"{symbol} {timeframe} 미완료 캔들 업데이트 실패: {str(e)}")

    def save_db_balance_data(self, balance_data):
        with self.session_scope() as session:
            session.query(BalanceData).delete()
            balance = BalanceData(
                wallet=balance_data['wallet'],
                total=balance_data['total'],
                free=balance_data['free'],
                used=balance_data['used'],
                pnl=balance_data['PNL']
            )
            session.add(balance)
            # logger.info("Balance data saved")


    def save_db_position_data(self, position_data):
        with self.session_scope() as session:
            position = session.query(PositionData).filter_by(symbol=position_data['symbol']).first()
            if position:
                # 기존 데이터 업데이트
                position.avg_price = position_data['avg_price']
                position.position_amount = position_data['position_amount']
                position.leverage = position_data['leverage']
                position.unrealized_profit = position_data['unrealizedProfit']
                position.breakeven_price = position_data['breakeven_price']
                # 'market_status'가 제공된 경우에만 업데이트
                if 'market_status' in position_data:
                    position.market_status = position_data['market_status']
            else:
                # 새로운 데이터 추가
                market_status = position_data.get('market_status', 'Unknown')  # 기본값 'Unknown'
                position = PositionData(
                    symbol=position_data['symbol'],
                    avg_price=position_data['avg_price'],
                    position_amount=position_data['position_amount'],
                    leverage=position_data['leverage'],
                    unrealized_profit=position_data['unrealizedProfit'],
                    breakeven_price=position_data['breakeven_price'],
                    market_status=market_status
                )
                session.add(position)
            # logger.info(f"Position data saved for {position_data['symbol']}")


    def get_position_data_by_symbol(self,symbol):
        session = Session()
        try:
            position = session.query(PositionData).filter_by(symbol=symbol).first()
            if position:
                position_dict = {
                    "symbol": position.symbol,
                    "avg_price": position.avg_price,
                    "position_amount": position.position_amount,
                    "leverage": position.leverage,
                    "unrealized_profit": position.unrealized_profit,
                    "breakeven_price": position.breakeven_price,
                    "market_status": position.market_status
                }
                print(symbol, position_dict)
                return position_dict
            else:
                print(f"No position found for symbol: {symbol}")
                return None
        except Exception as e:
            print(f"Error getting position data: {str(e)}")
        finally:
            session.close()

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # DataHandler 인스턴스 생성 및 테스트 실행
    # data_handler = DataHandler()
    
    test_market_status = {
        'symbol': 'BTCUSDT',
        'market_status_long': 'BULLISH',
        'market_status_short': 'BEARISH'
    }
    DataHandler.save_db_market_status(test_market_status)
    
    test_balance_data = {
        'wallet': 1000.0,
        'total': 1200.0,
        'free': 800.0,
        'used': 200.0,
        'PNL': 50.0
    }
    DataHandler.save_db_balance_data(test_balance_data)
    
    test_position_data = {
        'symbol': 'BTCUSDT',
        'avg_price': 50000.0,
        'position_amount': 0.5,
        'leverage': 20,
        'unrealizedProfit': 100.0,
        'breakeven_price': 49500.0
    }
    DataHandler.save_db_position_data(test_position_data)
    
    # 프로그램이 종료되지 않고 스레드를 유지하도록 대기
    while True:
        time.sleep(60)