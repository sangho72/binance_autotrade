import json
import os
import signal
import threading
import time
from logger import logger
from config import COIN_LIST,BASE_DIR
from data_handler import DataHandler
from order_handler import OrderHandler
from basic_strategy import BasicStrategy
from ws_manager import WebSocketManager
from indicators import Indicators
from time_sync import TimeSync

import schedule
import traceback
STATUS_FILE = os.path.join(BASE_DIR, "bot_status.json")

class TradingBot:
    def __init__(self):
        self.running = False
        self.marketstatus = None
        self.signals = {symbol: {} for symbol in COIN_LIST}
        self.orderbook = {symbol: {} for symbol in COIN_LIST}
        self.data_handler = DataHandler()
        self.ws_manager = WebSocketManager(self.data_handler, self.orderbook, self.signals)
        self.order_handler = OrderHandler(self.data_handler, self.ws_manager)
        self.strategy = BasicStrategy(self.data_handler)
        self.time_sync = TimeSync()
        self.indicators = Indicators()
        self.balance_data = self.data_handler.balance_data
        self.position_data = self.data_handler.position_data

    def run(self):
        self.running = True
        self.update_status({"status": "running", "pid": os.getpid()})
        try:
            self.time_sync.sync_system_time()  
            
            # 1시간마다 시간 차이 체크 (기존 스케줄러 설정)
            schedule.every(1).hour.at(":01").do(
                lambda: self.time_sync.check_time_diff()
            )
            self.data_handler.initialize_data() 

            self.ws_manager.start_account_websocket()  # 계정 업데이트
            self.ws_manager.start_coin_websockets()    # 코인별 3개 웹소켓
            time.sleep(5)

            while self.running:
                self.trade_cycle()
                time.sleep(0.5)
                schedule.run_pending()
        except Exception as e:
            logger.error(f"TradingBot error: {str(e)}")
            traceback.print_exc()
        finally:
            self.stop()
    
    def stop(self):
        if self.running:  # 중복 호출 방지
            self.running = False
            self.ws_manager.stop_all()
            self.update_status({"status": "stopped", "pid": None})
            logger.info("Trading bot stopped cleanly.")

    def stop1(self):
        self.running = False
        self.ws_manager.stop_all()
        self.update_status({"status": "stopped", "pid": None})
        logger.info("Trading bot stopped.")    

    def trade_cycle(self):
        """매매 주기 실행"""
        for symbol in self.data_handler.coin_data.keys():
            # 데이터 가져오기
            df_1m = self.data_handler.coin_data[symbol]['1m']
            df_1h = self.data_handler.coin_data[symbol]['15m']
            # 지표 계산
            df_1m = self.indicators.calculate_indicators(df_1m)
            df_1h = self.indicators.calculate_indicators(df_1h)
            # print(df_1m)
            # 시장 상태 분석
            market_status_long = self.indicators.determine_market_status(df_1h)
            market_status_short = self.indicators.determine_market_status(df_1m)
            market_status = {'symbol' : symbol,'market_status_long': market_status_long,'market_status_short': market_status_short}
            self.data_handler.save_db_market_status(market_status)
            self.marketstatus = market_status_short
            
            # tick_size = self.data_handler.tick_size[symbol]

            orderbook_data = self.data_handler.orderbook_data[symbol]
            orderbook = self.indicators.calculate_orderbook_indicators(orderbook_data)

            # orderbook['tick_size'] = tick_size
            # orderbook['market_status_1h'] = market_status_1h
            # orderbook['market_status_1m'] = market_status_1m
            # print(orderbook)
            # 매매 신호 생성
            position = self.data_handler.position_data[symbol]
            # position['market_status_1h'] = market_status_1h
            position['symbol'] = symbol
            position['market_status'] = market_status_short
            self.data_handler.position_data[symbol] = position
            self.data_handler.save_db_position_data(position)
            
            signals = self.strategy.generate_trading_signals(df_1m, position, orderbook)
            # print(f"{symbol} 매매 신호: {signals}")

            self.signals[symbol] = signals.copy()
            self.orderbook[symbol] = orderbook.copy()

            # 신호에 따라 매매 실행
            if position['position_amount'] == 0:
                if signals['action'] == 'ENTER_LONG':
                    self.order_handler.enter_long(symbol, signals)
                elif signals['action'] == 'ENTER_SHORT':
                    self.order_handler.enter_short(symbol, signals)
                    continue
            elif position['position_amount'] > 0:
                if signals['action'] == 'ENTER_LONG':
                    self.order_handler.enter_long(symbol, signals)
                elif signals['action'] == 'EXIT_LONG':
                    self.order_handler.exit_long(symbol, signals)
                    continue
            elif position['position_amount'] < 0:
                if signals['action'] == 'EXIT_SHORT':
                    self.order_handler.exit_short(symbol, signals)
                elif signals['action'] == 'ENTER_SHORT':
                    self.order_handler.enter_short(symbol, signals)
            time.sleep(1)

    def update_status(self, status):
        with open(STATUS_FILE, "w") as f:
            json.dump(status, f)

def signal_handler(signum, frame):
    global bot
    logger.info(f"Received signal {signum}, stopping bot...")
    bot.stop()

def signal_handler1(signum, frame):
    bot.stop()

if __name__ == "__main__":
    bot = TradingBot()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    bot.run()
