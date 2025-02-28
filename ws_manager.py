import os
import time
import pandas as pd
import websocket
import json
import threading
from config import COIN_LIST, API_KEY, SECRET_KEY, DATA_DIR
from data_handler import DataHandler
from logger import logger
from datetime import datetime, timedelta
from binance.client import Client


class WebSocketManager:
    def __init__(self, data_handler: DataHandler, orderbook,signals):
        try:
            self.data_handler = data_handler
            self.ws_connections = []  # 실제 WebSocketApp 객체들을 저장
            self.ws_threads = []      # WebSocket 스레드들을 저장            
            self.orderbook = orderbook
            self.signals = signals
            self.stop_event = threading.Event()
            # 계정 업데이트 웹소켓 별도 관리
            self.account_ws = None
            
            logger.system("WebSocketManager 초기화 완료")
        except Exception as e:
            logger.error(f"WebSocketManager 초기화 실패: {str(e)}")
            raise

    def _start_single_websocket(self, url, on_message):
        """개별 웹소켓 연결 관리"""
        def run():
            while not self.stop_event.is_set():
                try:
                    ws = websocket.WebSocketApp(
                        url,
                        on_message=on_message,
                        on_error=self.on_error,
                        on_close=self.on_close
                    )

                    self.ws_connections.append(ws)
                    ws.run_forever()

                    # 중지 이벤트가 설정되었다면 루프 종료
                    if self.stop_event.is_set():
                        break
                except Exception as e:
                    logger.error(f"WebSocket connection failed: {str(e)}")
                    if not self.stop_event.is_set():
                        time.sleep(5)  # 재연결 대기
                    else:
                        break

        thread = threading.Thread(target=run, daemon=True)
        thread.name = f"{url}"
        self.ws_threads.append(thread)  # 스레드 저장
        thread.start()
        return thread


    def get_order_by_order_id(self,symbol: str, order_id: int):
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
            order = client.get_order(symbol=symbol, orderId=order_id)
            return order
        except Exception as e:
            error_message = f"주문 조회 중 오류 발생: {e}"
            print(error_message)
            return {"error": error_message}

    # 기존 on_message_account_update 로직 완전 재현
    def _on_account_update(self, ws, message):
        data = json.loads(message)
        event_type = data.get('e')
        event_time_timestamp = int(data.get("E", 0)) / 1000  # 밀리초 단위의 타임스탬프를 초 단위로 변환
        event_time_datetime = datetime.fromtimestamp(event_time_timestamp) # timestamp를 datetime 객체로 변환
        # event_time = event_time_datetime + timedelta(hours=9) # datetime 객체에 timedelta를 더함
        event_time_str = event_time_datetime.strftime('%Y-%m-%d %H:%M:%S') # strftime은 datetime 객체에 사용
        if event_type == "ACCOUNT_CONFIG_UPDATE":
            # print(data)
            symbol = data.get('ac').get('s')  # 'a'와 'B' 키를 안전하게 가져옴
            if symbol not in self.data_handler.position_data:
                self.data_handler.position_data[symbol] = {'leverage': 0, 'avg_price': 0, 'position_amount': 0, 'unrealizedProfit': 0, 'breakeven_price': 0}
                self.data_handler.position_data_update(symbol)
                COIN_LIST.append(symbol)
                time.sleep(1)
            leverage = data.get('ac').get('l')
            self.data_handler.position_data[symbol]['leverage'] = leverage
            print(symbol,event_type,self.data_handler.position_data[symbol])

        elif event_type == "ACCOUNT_UPDATE":
            # print("ACCOUNT_UPDATE 이벤트 발생!")
            # print(data)
            wallets = data.get('a', {}).get('B', [])  # 'a'와 'B' 키를 안전하게 가져옴
            reason_type = data.get('a').get('m')
            for wallet in wallets:
                if wallet.get('a') == 'USDT':
                    total_wallet_balance = float(wallet.get('wb',0))  # 'wb' 값을 가져옴
                    Balance_Change = float(wallet.get('bc', 0))
                    self.data_handler.balance_data['wallet']=total_wallet_balance
                    # print('wallet_balance',total_wallet_balance,Balance_Change)
                    break
                
            positions = data.get('a', {}).get('P', [])  # 'P' 역시 리스트로 처리
            for position in positions:
                symbol = position.get("s")
                if symbol not in self.data_handler.position_data:
                    self.data_handler.position_data_update(symbol)
                    time.sleep(1)

                self.data_handler.position_data[symbol].update({
                    'avg_price': float(position.get("ep")),
                    'position_amount': float(position.get("pa")),
                    'unrealizedProfit': float(position.get("up")),
                    'breakeven_price': float(position.get("bep", 0) or 0)
                    })


            if Balance_Change != 0:
                event_reason = f"{reason_type} {Balance_Change:.4f}" if Balance_Change != 0 else None
                self.data_handler.balance_data_update(event_reason)

        elif event_type == "ORDER_TRADE_UPDATE":
            order_data = data.get("o")
            symbol = order_data.get("s")
            order_id = order_data.get("i")
            side = order_data.get("S")
            order_status = order_data.get("X")

            # FILLED 상태면 최종 처리
            if order_status == 'FILLED':
                # print(order_data)
                event_reason = None
                position_amount=self.data_handler.position_data[symbol]['position_amount']
                position_price = self.data_handler.position_data[symbol]['avg_price']
                leverage = float(self.data_handler.position_data[symbol]['leverage'])
                Wallet = self.data_handler.balance_data['wallet']

                avg_price = float(order_data.get("ap", 0))
                original_quantity = float(order_data.get("q", 0))
                accumulated_quantity = float(order_data.get("z", 0))
                realized_profit = float(order_data.get("rp", 0))
                commission = float(order_data.get("n", 0))
                total_cost = accumulated_quantity * avg_price
                initialMargin = total_cost / leverage

                if self.signals[symbol]['action'] == 'HOLD':
                    action = side
                    reason  = ''
                else:
                    action = self.signals[symbol]['action']
                    reason  = self.signals[symbol]['reason']

                trade = (
                    f"Wallet : {Wallet:.4f} USDT\n" 
                    f"Action:\t {symbol} - {action}\n"
                    f"가  격:\t {avg_price:.5f}\n"
                    f"거래량:\t {accumulated_quantity*avg_price:.4f} USDT \t{leverage}\n"
                )
                if position_amount != 0:
                    trade += f"포지션:\t {position_amount*position_price:.4f} USDT\n"
                if realized_profit != 0:
                    trade += f"수  익:\t {realized_profit:.4f} USDT, {realized_profit/initialMargin*100:.4f} %\n"
                    event_reason = f"{symbol} {realized_profit:.4f}" if realized_profit != 0 else None
                if commission != 0:
                    trade += f"수수료:\t {commission:.4f} USDT\n"
                if reason:
                    trade += f"Reason:\t {reason}\n"

                self.data_handler.balance_data_update(event_reason)
                self.data_handler.position_data_update(symbol)
                trade_info = (
                    f"{trade} \n"
                    f"balance\t{self.data_handler.balance_data}\n"
                    f"position\t{self.data_handler.position_data[symbol]}\n"
                    f"orderbook\t{self.orderbook[symbol]}\n"
                    f"signal\t{self.signals[symbol]}\n"
                )

                # print(trade_info)
                logger.send_telegram_alert_sync(trade)
                self.trade_history(trade_info)
                # logger.trade(trade)
                # 최종 처리 후 데이터 초기화


    def trade_history(self,trade):
        with open("my_bot/binance_trade_history.txt", "a", encoding="utf-8") as fp:
            fp.write(trade)  # 파일에 잔액 정보 기록
            fp.write('\n')  # 새로운 줄 추가
        return

    # 기존 on_message_orderbook 로직 재현
    def _on_orderbook(self, ws, message):
        data = json.loads(message)
        symbol = data['s']
        with self.data_handler.lock:
            self.data_handler.orderbook_data[symbol] = data
            self.data_handler.save_orderbook_data(symbol)

    # 기존 on_message_1m/1h 캔들 처리 재현
    def _on_kline(self, ws, message, timeframe, save_to_file=True):
        data = json.loads(message)
        kline = data['k']
        symbol = data['s']
        # open_time = pd.to_datetime(candle['t'], unit='ms') + pd.Timedelta(hours=9)  # UTC+9로 변환
        # open_time_str = open_time.strftime('%Y-%m-%d %H:%M')  # 형식 변환

        with self.data_handler.lock:
            if self.data_handler.coin_data[symbol][timeframe].empty:
                self.data_handler.coin_data[symbol][timeframe] = pd.DataFrame(columns=[
                    'Open time', 'Open', 'High', 'Low', 'Close', 'Volume'
                ])
                
            df = self.data_handler.coin_data[symbol][timeframe]

            # 신규 데이터 생성
            new_row = {
                'Open time': pd.to_datetime(kline['t'], unit='ms') + pd.Timedelta(hours=9),
                'Open': float(kline['o']),
                'High': float(kline['h']),
                'Low': float(kline['l']),
                'Close': float(kline['c']),
                'Volume': float(kline['v'])
            }

            self.data_handler._update_incomplete_candle_in_db(symbol, timeframe, new_row)

            # 데이터 업데이트
            if kline['x']:  # 캔들 종료
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                if len(df) > 60:
                    df = df.iloc[1:]  # 80개의 최신 데이터 유지
                # DB에 신규 캔들 추가
                # self.data_handler._update_incomplete_candle_in_db(symbol, timeframe, new_row)

            else:  # 캔들 업데이트
                if not df.empty:
                    df.loc[df.index[-1], ['Open time', 'Open', 'High', 'Low', 'Close', 'Volume']] = [
                        new_row['Open time'], new_row['Open'], new_row['High'], 
                        new_row['Low'], new_row['Close'], new_row['Volume']
                    ]
                    self.data_handler.coin_data[symbol][timeframe] = df
                    # DB에서 마지막 캔들 업데이트
                    # self.data_handler._update_incomplete_candle_in_db(symbol, timeframe, new_row)

            # 파일로 저장 (옵션)
            if save_to_file:
                file_path = os.path.join(DATA_DIR, f"klines_{symbol}_{timeframe}.csv")
                df.to_csv(file_path, index=False, sep='\t')

    def start_account_websocket(self):
        """계정 업데이트 웹소켓 (기존 start_account_update_websocket 재현)"""
        listen_key = self.data_handler.client.futures_stream_get_listen_key()
        url = f"wss://fstream.binance.com/ws/{listen_key}"
        self.account_ws = self._start_single_websocket(url, self._on_account_update)
        

    def start_coin_websockets(self):
        """코인별 웹소켓 3개씩 생성 (기존 start_websocket 함수 재현)"""
        for symbol in COIN_LIST:
            symbol_lower = symbol.lower()
            
            # 1. 오더북 웹소켓
            self._start_single_websocket(
                f"wss://fstream.binance.com/ws/{symbol_lower}@depth20@500ms",
                self._on_orderbook
            )
            
            # 2. 1분 캔들 웹소켓
            self._start_single_websocket(
                f"wss://fstream.binance.com/ws/{symbol_lower}@kline_1m",
                lambda ws, msg: self._on_kline(ws, msg, '1m')
            )
            
            # 3. 1시간 캔들 웹소켓
            self._start_single_websocket(
                f"wss://fstream.binance.com/ws/{symbol_lower}@kline_15m",
                lambda ws, msg: self._on_kline(ws, msg, '15m')
            )
            # time.sleep(1)

    def on_error(self, ws, error):
        logger.error(f"웹소켓 에러: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        logger.error(f"웹소켓 연결 종료: {close_status_code} - {close_msg}")


    def stop_all(self):
        """모든 WebSocket 연결 종료"""
        try:
            # 중지 이벤트 설정
            self.stop_event.set()
            
            # 계정 웹소켓 종료
            if self.account_ws and hasattr(self.account_ws, 'close'):
                self.account_ws.close()
            
            # 모든 웹소켓 연결 종료
            for ws in self.ws_connections:
                if ws and hasattr(ws, 'close'):
                    ws.close()

            # 스레드 종료 대기
            for thread in self.ws_threads:
                if thread and thread.is_alive():
                    thread.join(timeout=2)

            # 연결 목록 초기화
            self.ws_connections.clear()
            self.ws_threads.clear()

            # Logger 종료 호출
            logger.stop()

            logger.info("All WebSocket connections closed")
            return True
            
        except Exception as e:
            logger.error(f"Error closing WebSocket connections: {str(e)}")
            return False
                         
