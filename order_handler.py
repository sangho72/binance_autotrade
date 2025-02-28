from binance.client import Client
from binance.exceptions import BinanceAPIException
from decimal import Decimal
from data_handler import DataHandler
from ws_manager import WebSocketManager
from config import API_KEY, SECRET_KEY, TARGET_LEVERAGE, TRADE_RATE
from logger import logger
import threading
import time
from datetime import datetime, timedelta,timezone


class OrderHandler:
    def __init__(self, data_handler,ws_manager):
        self.client = Client(API_KEY, SECRET_KEY)
        self.data_handler = data_handler
        self.ws_manager = ws_manager
        self.lock = threading.Lock()
        logger.system(f"OrderHandler Class 시작")
        self.nowtime = datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S')
    def set_leverage(self, symbol):
        """레버리지 설정 (기존 로직 유지)"""
        try:
            self.client.futures_change_leverage(
                symbol=symbol, 
                leverage=TARGET_LEVERAGE
            )
        except BinanceAPIException as e:
            logger.error(f"{symbol} 레버리지 설정 실패: {e}")

    def cancel_all_orders(self, symbol):
        """모든 오더 취소 (기존 로직 유지)"""
        try:
            self.client.futures_cancel_all_open_orders(symbol=symbol)
            logger.system(f"{symbol} 모든 오더 취소 완료")
        except BinanceAPIException as e:
            logger.error(f"{symbol} 오더 취소 실패: {e}")

    def calculate_order_amount(self, symbol):
        """주문 금액 계산 (기존 트레이드 레이트 적용)"""
        balance = float(self.data_handler.balance_data['wallet'])
        price = self.data_handler.coin_data[symbol]['1m']['Close'].iloc[-1]
        return round((balance * TRADE_RATE * TARGET_LEVERAGE) / price, 2)

    def get_order_by_order_id(self, symbol: str, order_id: int):
        """
        주어진 심볼과 주문 ID를 기반으로 Binance에서 주문 정보를 조회합니다.
        
        Args:
            symbol (str): 거래쌍 심볼 (예: 'BTCUSDT')
            order_id (int): 조회할 주문의 order_id
            
        Returns:
            dict: 주문 정보가 담긴 dict.
                오류 발생 시 error 키가 포함된 dict가 반환됩니다.
        """
        try:
            client = Client(API_KEY, SECRET_KEY)
            # Binance API에서 주문 정보 조회 (주문 조회 엔드포인트 사용)
            order = self.client.get_order(symbol=symbol, orderId=order_id)
            return order
        except Exception as e:
            error_message = f"주문 조회 중 오류 발생: {e}"
            print(error_message)
            return {"error": error_message}
    #▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
    # 기존 longstart/longend/shortstart/shortend 함수 리팩토링
    #▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲

    def enter_long(self, symbol, signal):
        """롱 포지션 진입 (기존 longstart 함수 대체)"""
        try:

            order = self.client.futures_create_order(
                symbol=symbol,
                side='BUY',
                type='LIMIT',
                quantity=signal['amount'],
                price=signal['price'],
                timeInForce='GTC'
            )
            time.sleep(1)

            # 롱 진입 주문 완료 후 signal 정보를 그대로 전달하여 trailing stop 주문 설정
            # ts_order = self.set_trailing_stop(signal)

             # print(order)
            
        except Exception as e:
            logger.error(f"{symbol}enter_long {e}")
            return

    def exit_long(self, symbol, signal):
        """롱 포지션 청산 (기존 longend 함수 대체)"""
        open_orders = self.client.futures_get_open_orders(symbol=symbol)
        for order in open_orders:
            print(f"Cancelling open order {order['orderId']}")
            self.client.futures_cancel_order(symbol=symbol, orderId=order['orderId'])

        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side='SELL',
                type='LIMIT',
                quantity=signal['amount'],
                price=signal['price'],
                timeInForce='GTC'
            )
            time.sleep(1)
            # print(order)

        except Exception as e:
            logger.error(f"{symbol}exit_long {e}")
            return

    def enter_short(self, symbol, signal):
        """숏 포지션 진입 (기존 shortstart 함수 대체)"""
        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side='SELL',
                type='LIMIT',
                quantity=signal['amount'],
                price=signal['price'],
                timeInForce='GTC'
            )
            time.sleep(1)
            # 주문 완료 후 signal 정보를 그대로 전달하여 trailing stop 주문 설정
            # ts_order = self.set_trailing_stop(signal)
             # print(order)

        except Exception as e:
            logger.error(f"{symbol}enter_short {e}")
            return

    def exit_short(self, symbol, signal):
        """숏 포지션 청산 (기존 shortend 함수 대체)"""
        open_orders = self.client.futures_get_open_orders(symbol=symbol)
        for order in open_orders:
            print(f"Cancelling open order {order['orderId']}")
            self.client.futures_cancel_order(symbol=symbol, orderId=order['orderId'])
        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side='BUY',
                type='LIMIT',
                quantity=abs(signal['amount']),
                price=signal['price'],
                timeInForce='GTC'
            )
            time.sleep(1)
            # print(order)

            time.sleep(1)
        except Exception as e:
            logger.error(f"{symbol}exit_short {e}")
            return

       
    def set_trailing_stop(self, signal):
        """
        signal 정보를 이용하여 트레일링 스탑 주문을 설정하는 함수.
        signal에는 'symbol', 'price', 'action', 'amount' 등의 정보가 포함되어 있음.
        
        롱 포지션인 경우(예: signal의 action이 'enter_long' 등인 경우) trailing stop 주문은 SELL,
        숏 포지션인 경우 trailing stop 주문은 BUY로 설정합니다.
        
        여기서는 예시로 signal['price']의 0.99배를 activationPrice로, callbackRate는 1%로 설정합니다.
        실제 전략에서는 이 값들을 상황에 맞게 동적으로 계산하도록 수정할 수 있습니다.
        """
        try:
            symbol = signal['symbol']
            
            # signal의 가격 정보를 활용하여 activationPrice 및 callbackRate 산정
            activationPrice = float(signal['price'])   # 예: 진입 가격의 0.99배
            callbackRate = 2.0  # 예: 1% (전략에 따라 조정)
            
            # 현재 포지션 정보에 따라 주문 side 결정 (롱이면 SELL, 숏이면 BUY)
            side = 'SELL' if signal['action'] == 'enter_long' else 'BUY'
            
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type='TRAILING_STOP_MARKET',
                activationPrice=activationPrice,
                callbackRate=callbackRate,
                quantity=float(signal['amount'])
            )
            # print(f"{symbol} 트레일링 스탑 설정 완료: {order}")
            return order
        except Exception as e:
            logger.error(f"{symbol} 트레일링 스탑 설정 실패: {e}")
            return None
