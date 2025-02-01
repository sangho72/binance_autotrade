import websocket
import time
import hmac
import hashlib
import json
import threading
import pandas as pd
import requests
import os
import sqlite3
from datetime import datetime, timedelta
from config import BINANCE_API_KEY, BINANCE_SECRET_KEY,COIN_LIST, datetime, KST
from position_check import balance_data,position_data,position_check,balance_check
from database import coin_data,get_symbol_coin_data,get_db_connection

# 전역 변수를 초기화
orderbook_data = {symbol: [] for symbol in COIN_LIST}
lock = threading.Lock()

BASE_URL = "https://fapi.binance.com"

def position_data_update(symbol):
    url = f"{BASE_URL}/fapi/v2/positionRisk"

    # 타임스탬프와 서명 생성
    timestamp = int(time.time() * 1000)
    query_string = f"symbol={symbol}&timestamp={timestamp}"
    signature = hmac.new(
        BINANCE_SECRET_KEY.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    # 요청 헤더 설정
    headers = {
        "X-MBX-APIKEY": BINANCE_API_KEY
    }

    # 요청 보내기
    response = requests.get(url, headers=headers, params={"symbol": symbol, "timestamp": timestamp, "signature": signature})

    # 결과 반환
    if response.status_code == 200:
        data = response.json()
        if data:
            position_data[symbol] = {
                "avg_price": float(data[0]['entryPrice']),
                "position_amount": float(data[0]['positionAmt']),
                "leverage": int(data[0]['leverage']),
                "unrealizedProfit": float(data[0]['unRealizedProfit']),
                "breakeven_price": float(data[0]['breakEvenPrice'])
            }
            print(symbol,position_data[symbol])
            return position_data[symbol]
    else:
        print(f"Error fetching leverage for {symbol}: {response.text}")
    return None

# ACCOUNT_UPDATE 메시지 핸들러
order_accumulation = {} # 체결 정보를 저장할 딕셔너리
def on_message_account_update(ws, message):
    nowtime = datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')
    # global usdt_free
    # global total_wallet_balance
    data = json.loads(message)
    event_type = data.get("e")
    # print(data)
    # print(position_data)
    if event_type == "ACCOUNT_CONFIG_UPDATE":
        # print(data)
        symbol = data.get('ac').get('s')  # 'a'와 'B' 키를 안전하게 가져옴
        if symbol not in position_data:
            position_data[symbol] = {'leverage': 0, 'avg_price': 0, 'position_amount': 0, 'unrealizedProfit': 0, 'breakeven_price': 0}
            position_data_update(symbol)
        leverage = data.get('ac').get('l')
        position_data[symbol]['leverage'] = leverage
        print(symbol,event_type,position_data[symbol])
            
    if event_type == "ACCOUNT_UPDATE":
        # print("ACCOUNT_UPDATE 이벤트 발생!")
        # print(data)
        wallets = data.get('a', {}).get('B', [])  # 'a'와 'B' 키를 안전하게 가져옴
        reason_type = data.get('a').get('m')
        for wallet in wallets:
            if wallet.get('a') == 'USDT':
                total_wallet_balance = float(wallet.get('wb',0))  # 'wb' 값을 가져옴
                Balance_Change = float(wallet.get('bc', 0))
                balance_data['wallet']=total_wallet_balance
                print('wallet_balance',total_wallet_balance,Balance_Change)
                break
            
        positions = data.get('a', {}).get('P', [])  # 'P' 역시 리스트로 처리
        for position in positions:
            symbol = position.get("s")
            if symbol not in position_data:
                position_data[symbol] = position_data_update(symbol)
            position_data[symbol]['avg_price']=float(position.get("ep"))
            position_data[symbol]['position_amount']=float(position.get("pa"))
            position_data[symbol]['unrealizedProfit']=float(position.get("up"))
            position_data[symbol]['breakeven_price'] = float(position.get("bep", 0) or 0)
            print(symbol,position_data[symbol])

        if Balance_Change != 0:
            event_reason = f"{reason_type} {Balance_Change:.4f}" if Balance_Change != 0 else None
            balance_check(event_reason)

    elif event_type == "ORDER_TRADE_UPDATE":
        # print(data)
        order_data = data.get("o")
        symbol = order_data.get("s")
        side = order_data.get("S")
        order_status = order_data.get("X")
        last_filled_quantity = float(order_data.get("l", 0))  # 방금 체결된 수량
        last_trade_price = float(order_data.get("L", 0))  # 방금 체결된 가격
        last_profit = float(order_data.get("rp", 0))  # 방금 체결된 수익
        # commossion = float(order_data.get("n", 0))
        # 주문 정보 누적 관리
        if symbol not in order_accumulation:
            # 초기화: 각 체결량, 가격, 수익을 누적할 구조 생성
            order_accumulation[symbol] = {
                "total_quantity": 0,
                "total_cost": 0,
                "total_profit": 0
            }

        # 누적 업데이트
        order_accumulation[symbol]["total_quantity"] += last_filled_quantity
        order_accumulation[symbol]["total_cost"] += last_filled_quantity * last_trade_price
        order_accumulation[symbol]["total_profit"] += last_profit
        leverage = float(position_data[symbol]['leverage'])
        # FILLED 상태면 최종 처리
        if order_status == 'FILLED':
            accumulated = order_accumulation[symbol]
            total_quantity = accumulated["total_quantity"]
            avg_price = accumulated["total_cost"] / total_quantity if total_quantity > 0 else 0
            total_profit = accumulated["total_profit"]
            position_amount=position_data[symbol]['position_amount']
            trade = (
                f"{nowtime}  - {side} - \n" 
                f"코인명:\t {symbol}\n"
                f"가 격:\t {avg_price:.5f}\n"
                f"거래량:\t {total_quantity*avg_price:.4f} USDT \t{leverage}\n"
            )
            if position_amount != 0:
                trade += f"포지션:\t {position_amount*avg_price:.4f} USDT\n"

            if total_profit != 0:
                trade += f"수 익:\t {total_profit:.4f} USDT, {total_profit/(total_quantity*avg_price/leverage)*100:.4f} %\n"
                event_reason = f"{symbol} {total_profit:.4f}" if total_profit != 0 else None
                balance_check(event_reason)
            print(trade)
            trade_history(trade)
            # 최종 처리 후 데이터 초기화
            del order_accumulation[symbol]

def trade_history(trade):
    with open("Binance_autotrade\\binance_trade_history.txt", "a", encoding="utf-8") as fp:
        fp.write(trade)  # 파일에 잔액 정보 기록
        fp.write('\n')  # 새로운 줄 추가
    return

# def save_orderbook_data_to_db(symbol, df):
#     try:
#         conn = get_db_connection()
#         table_name = f"orderbook_{symbol}"
#         df.to_sql(table_name, conn, if_exists='replace', index=False)
#         conn.close()
#     except Exception as e:
#         print(f"Error saving orderbook data for {symbol} to database: {e}")

# Orderbook 업데이트용 웹소켓 메시지 핸들러
# def on_message_orderbook(ws, message):
#     try:
#         data = json.loads(message)
#         symbol = data['s']
#         event_time = datetime.fromtimestamp(data['E'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
#         bids = data['b']
#         asks = data['a']

#         # bids와 asks 데이터를 분리하여 데이터프레임 생성
#         bid_prices = [float(bid[0]) for bid in bids]
#         bid_qtys = [float(bid[1]) for bid in bids]
#         ask_prices = [float(ask[0]) for ask in asks]
#         ask_qtys = [float(ask[1]) for ask in asks]


#         orderbook_data[symbol] = {
#             # 'event_time': event_time,
#             'bid_price': json.dumps(bid_prices),
#             'bid_qty': json.dumps(bid_qtys),
#             'ask_price': json.dumps(ask_prices),
#             'ask_qty': json.dumps(ask_qtys)
#         }

#         df = pd.DataFrame([orderbook_data[symbol]])

#         # 데이터베이스에 저장
#         save_orderbook_data_to_db(symbol, df)
#     except Exception as e:
#         print(f"Error processing orderbook data: {e}")
def on_message_orderbook(ws, message):
    global orderbook_data
    data = json.loads(message)
    symbol = data['s']
    with lock:
        orderbook_data[symbol] = data  # 최신 orderbook 데이터를 전역 변수에 저장
    df = pd.DataFrame(orderbook_data[symbol])
    df.to_csv(f"Binance_autotrade\\coin_data\\orderbook_data_{symbol}.csv", index=False, sep='\t')

# 데이터프레임 업데이트 함수
# def update_dataframe(symbol, timeframe, candle_data, is_closed):
#     df = coin_data[symbol][timeframe]

#     # 캔들이 닫힌 경우
#     if is_closed:
#         df = pd.concat([df, pd.DataFrame([candle_data])], ignore_index=True)
#         if len(df) > 1000:
#             df = df.iloc[1:]  # 80개의 최신 데이터 유지
#     else:
#         # 닫히지 않은 경우 마지막 행 업데이트
#         if not df.empty:
#             df.iloc[-1] = candle_data
#         else:
#             # 데이터프레임이 비어 있는 경우 처음 데이터를 추가
#             df = pd.DataFrame([candle_data])

#     # 전역 변수에 저장 및 CSV로 저장
#     coin_data[symbol][timeframe] = df
#     data = pd.DataFrame(coin_data[symbol][timeframe])
#     data.to_csv(f"Binance_autotrade\\coin_data\\coin_data_{symbol}_{timeframe}.csv", index=False, sep='\t')

#     return coin_data
def update_dataframe(symbol, timeframe, candle_data, is_closed):
    # conn = get_db_connection()
    # cursor = conn.cursor()

    # table_name = f"coin_data_{symbol}_{timeframe}"

    # # 캔들이 닫힌 경우
    # if is_closed:
    #     cursor.execute(f'''
    #         INSERT OR REPLACE INTO {table_name} ('Open time', 'Open', 'High', 'Low', 'Close', 'Volume')
    #         VALUES (?, ?, ?, ?, ?, ?)
    #     ''', (candle_data['Open time'], candle_data['Open'], candle_data['High'], candle_data['Low'], candle_data['Close'], candle_data['Volume']))

    #     # 1000개의 최신 데이터 유지
    #     cursor.execute(f'''
    #         DELETE FROM {table_name}
    #         WHERE rowid NOT IN (
    #             SELECT rowid
    #             FROM {table_name}
    #             ORDER BY open_time DESC
    #             LIMIT 1000
    #         )
    #     ''')
    # else:
    #     # 닫히지 않은 경우 마지막 행 업데이트
    #     cursor.execute(f'''
    #         INSERT OR REPLACE INTO {table_name} ('Open time', 'Open', 'High', 'Low', 'Close', 'Volume')
    #         VALUES (?, ?, ?, ?, ?, ?)
    #     ''', (candle_data['Open time'], candle_data['Open'], candle_data['High'], candle_data['Low'], candle_data['Close'], candle_data['Volume']))


    df = coin_data[symbol][timeframe]

    # 캔들이 닫힌 경우
    if is_closed:
        df = pd.concat([df, pd.DataFrame([candle_data])], ignore_index=True)
        if len(df) > 1000:
            df = df.iloc[1:]  # 80개의 최신 데이터 유지
    else:
        # 닫히지 않은 경우 마지막 행 업데이트
        if not df.empty:
            df.iloc[-1] = candle_data
        else:
            # 데이터프레임이 비어 있는 경우 처음 데이터를 추가
            df = pd.DataFrame([candle_data])

    # 전역 변수에 저장 및 CSV로 저장
    coin_data[symbol][timeframe] = df
    data = pd.DataFrame(coin_data[symbol][timeframe])
    data.to_csv(f"Binance_autotrade\\coin_data\\coin_data_{symbol}_{timeframe}.csv", index=False, sep='\t')
    return coin_data

# update_dataframe함수에서 csv 에 저장하지 않고 coin_data.db에 업데이트 하도록 수정해주세요
# 1분 타임프레임 메시지 핸들러
def on_message_1m(ws, message):
    json_message = json.loads(message)
    candle = json_message['k']
    symbol = candle['s']
    open_time = pd.to_datetime(candle['t'], unit='ms') + pd.Timedelta(hours=9)  # UTC+9로 변환
    open_time_str = open_time.strftime('%Y-%m-%d %H:%M')  # 형식 변환
    candle_data = {
        'Open time': open_time_str,
        'Open': pd.to_numeric(pd.Series(candle['o']), errors='coerce')[0],
        'High': pd.to_numeric(pd.Series(candle['h']), errors='coerce')[0],
        'Low': pd.to_numeric(pd.Series(candle['l']), errors='coerce')[0],
        'Close': pd.to_numeric(pd.Series(candle['c']), errors='coerce')[0],
        'Volume': pd.to_numeric(pd.Series(candle['v']), errors='coerce')[0]
    }

    # 1분 데이터 업데이트
    update_dataframe(symbol, '1m', candle_data, candle['x'])

# 1시간 타임프레임 메시지 핸들러
def on_message_1h(ws, message):
    json_message = json.loads(message)
    candle = json_message['k']
    symbol = candle['s']
    open_time = pd.to_datetime(candle['t'], unit='ms') + pd.Timedelta(hours=9)  # UTC+9로 변환
    open_time_str = open_time.strftime('%Y-%m-%d %H:%M')  # 형식 변환
    candle_data = {
        'Open time': open_time_str,
        'Open': pd.to_numeric(pd.Series(candle['o']), errors='coerce')[0],
        'High': pd.to_numeric(pd.Series(candle['h']), errors='coerce')[0],
        'Low': pd.to_numeric(pd.Series(candle['l']), errors='coerce')[0],
        'Close': pd.to_numeric(pd.Series(candle['c']), errors='coerce')[0],
        'Volume': pd.to_numeric(pd.Series(candle['v']), errors='coerce')[0]
    }

    # 1시간 데이터 업데이트
    update_dataframe(symbol, '1h', candle_data, candle['x'])


# # 실시간 거래량 데이터 저장용 변수
# trade_data = {symbol: {"total_ask_volume": 0.0, "total_bid_volume": 0.0} for symbol in COIN_LIST}
# # 매수/매도 비율 저장용 변수
# get_trade_ratio = {symbol: 0.5 for symbol in COIN_LIST}  # 초기값은 0.5로 설정
# def on_message_trade(ws, message):
#     """
#     WebSocket으로 받은 메시지를 처리하여 매수/매도 비율 계산
#     """
#     try:
#         data = json.loads(message)
#         symbol = data.get("s")  # 심볼
#         is_bid = data.get("m", False)  # 매수/매도 여부
#         volume = float(data.get("q", 0))  # 거래량
#         event_time = datetime.fromtimestamp(data.get("E") / 1000)  # 이벤트 시간
#         if symbol not in trade_data:
#             trade_data[symbol] = {
#                 "total_ask_volume": 0.0,
#                 "total_bid_volume": 0.0
#             }

#         if is_bid:
#             trade_data[symbol]["total_ask_volume"] += volume
#         else:
#             trade_data[symbol]["total_bid_volume"] += volume

#         # 매수/매도 비율 계산
#         total_ask_volume = trade_data[symbol]["total_ask_volume"]
#         total_bid_volume = trade_data[symbol]["total_bid_volume"]
#         total_volume = total_ask_volume + total_bid_volume

#         if total_volume > 0:
#             get_trade_ratio[symbol] = total_bid_volume / total_volume
#         else:
#             get_trade_ratio[symbol] = 0.5  # 데이터 부족 시 중립값

#         # 데이터프레임 생성
#         df = pd.DataFrame([trade_data[symbol]])
#         df.to_csv(f"Binance_autotrade\\coin_data\\trade_data_{symbol}.csv", index=False, sep='\t')
#         # print(f"[{symbol}] 매수/매도 비율: {round(get_trade_ratio[symbol], 4)}")
#     except Exception as e:
#         print(f"Trade 데이터 처리 오류: {e}")
# trade_data = {}
# get_trade_ratio = {}
# def on_message_trade(ws, message):
#     try:
#         data = json.loads(message)
#         symbol = data.get("s")  # 심볼
#         price = float(data.get("p", 0))  # 가격
#         is_bid = data.get("m", False)  # 매수/매도 여부
#         volume = float(data.get("q", 0))  # 거래량
#         event_time = datetime.fromtimestamp(data.get("E") / 1000)  # 이벤트 시간

#         if symbol not in trade_data:
#             trade_data[symbol] = pd.DataFrame(columns=["event_time", "price", "is_bid", "volume"])

#         # 새로운 거래 데이터 추가
#         new_trade = pd.DataFrame([[event_time, price, is_bid, volume]], columns=["event_time", "price", "is_bid", "volume"])
        
#         # 빈 데이터프레임이나 모든 값이 NA인 항목을 제외하고 concat 수행
#         if not new_trade.empty and not new_trade.isna().all().all():
#             trade_data[symbol] = pd.concat([trade_data[symbol], new_trade], ignore_index=True)

#         # 최근 20분 동안의 데이터로 필터링
#         twenty_minutes_ago = datetime.now() - timedelta(minutes=20)
#         trade_data[symbol] = trade_data[symbol][trade_data[symbol]["event_time"] >= twenty_minutes_ago]

#         # 최근 10분 동안의 데이터로 매수/매도 비율 계산
#         ten_minutes_ago = datetime.now() - timedelta(minutes=10)
#         recent_trades = trade_data[symbol][trade_data[symbol]["event_time"] >= ten_minutes_ago]

#         # 매수/매도 비율 계산
#         total_ask_volume = recent_trades[recent_trades["is_bid"] == False]["volume"].sum()
#         total_bid_volume = recent_trades[recent_trades["is_bid"] == True]["volume"].sum()
#         total_volume = total_ask_volume + total_bid_volume

#         if total_volume > 0:
#             get_trade_ratio[symbol] = total_bid_volume / total_volume
#         else:
#             get_trade_ratio[symbol] = 0.5  # 데이터 부족 시 중립값

#         # 데이터프레임을 CSV 파일로 저장
#         trade_data[symbol].to_csv(f"Binance_autotrade\\coin_data\\trade_data_{symbol}.csv", index=False, sep='\t')
#         # print(f"[{symbol}] 매수/매도 비율: {round(get_trade_ratio[symbol], 4)}")
#     except Exception as e:
#         print(f"Trade 데이터 처리 오류: {e}")

def on_error(thread_name, error):
    print(f"[Error] Thread: {thread_name}, WebSocket Error: {error}")

def on_close(thread_name):
    print(f"[Close] Thread: {thread_name}, WebSocket connection closed.")
    time.sleep(5)
# 리슨키 웹소켓 연결
# def start_account_update_websocket():
#     listen_key = get_listen_key()
#     threading.Thread(target=keep_alive_listen_key, args=(listen_key,), daemon=True).start()

#     ws_url = f"wss://fstream.binance.com/ws/{listen_key}"
#     ws = websocket.WebSocketApp(
#         ws_url,
#         on_message=on_message_account_update,
#         on_error=on_error,
#         on_close=on_close,
#     )
#     threading.Thread(target=ws.run_forever).start()

# 리슨키 발급 및 갱신 함수
def get_listen_key():
    url = f"{BASE_URL}/fapi/v1/listenKey"
    response = requests.post(url, headers={"X-MBX-APIKEY": BINANCE_API_KEY})
    response.raise_for_status()
    return response.json()['listenKey']

def keep_alive_listen_key(listen_key):
    url = f"{BASE_URL}/fapi/v1/listenKey"
    while True:
        try:
            response = requests.put(url, headers={"X-MBX-APIKEY": BINANCE_API_KEY}, data={"listenKey": listen_key})
            response.raise_for_status()
            print("리슨키가 연장되었습니다.")
        except Exception as e:
            print(f"리슨키 갱신 중 오류 발생: {e}")
        time.sleep(30 * 60)  # 30분마다 갱신

# def start_account_update_websocket():
#     try:
#         listen_key = get_listen_key()
#         threading.Thread(target=keep_alive_listen_key, args=(listen_key,), name="KeepAliveListenKey", daemon=True).start()

#         thread_name = "AccountUpdateWebSocket"
#         ws_url = f"wss://fstream.binance.com/ws/{listen_key}"
#         ws = websocket.WebSocketApp(
#             ws_url,
#             on_message=on_message_account_update,
#             on_error=on_error,
#             on_close=on_close,
#         )
#         threading.Thread(target=ws.run_forever, name=thread_name).start()
#     except Exception as e:
#         print(f"Error starting account update websocket: {e}")
#         time.sleep(5)  # 재시작 전에 잠시 대기
#         start_account_update_websocket()  # 재시작
#     return thread_name

def start_account_update_websocket():
    def handle_websocket(thread_name, ws_url, listen_key):
        try:
            ws = websocket.WebSocketApp(
                ws_url,
                on_message=on_message_account_update,
                on_error=lambda ws, error: on_error(thread_name, error),
                on_close=lambda ws, *_: on_close(thread_name),
            )
            ws.run_forever()
        except Exception as e:
            print(f"[Exception] Thread: {thread_name}, WebSocket Error: {e}")
            time.sleep(5)  # 재시작 전에 잠시 대기
            start_account_update_websocket()  # 재시작

    try:
        listen_key = get_listen_key()
        threading.Thread(
            target=keep_alive_listen_key, 
            args=(listen_key,), 
            name="KeepAliveListenKey", 
            daemon=True
        ).start()

        thread_name = "AccountUpdateWebSocket"
        ws_url = f"wss://fstream.binance.com/ws/{listen_key}"
        threading.Thread(
            target=handle_websocket, 
            args=(thread_name, ws_url, listen_key), 
            name=thread_name, 
            daemon=True
        ).start()
    except Exception as e:
        print(f"Error starting account update websocket: {e}")
        time.sleep(5)  # 재시작 전에 잠시 대기
        start_account_update_websocket()  # 재시작
    return thread_name

# 스레드 관리를 위한 딕셔너리
threads = {}

def start_websocket(symbol_lower):
    def run_websocket(thread_name, socket_url, on_message, on_error, on_close):
        while True:
            try:
                ws = websocket.WebSocketApp(
                    socket_url,
                    on_message=on_message,
                    on_error=lambda ws, error: on_error(thread_name, error),
                    on_close=lambda ws, *_: on_close(thread_name)
                )
                ws.run_forever()
                time.sleep(0.5)
            except Exception as e:
                print(f"[Exception] Thread: {thread_name}, WebSocket Error: {e}")
                time.sleep(5)  # 재시작 전에 잠시 대기

    # 실시간 거래 데이터(WebSocket) 실행
    # thread_name = f'aggTrade_{symbol_lower}'
    # socket_url_trade = f'wss://fstream.binance.com/ws/{symbol_lower}@aggTrade'
    # trade_thread = threading.Thread(
    #     target=run_websocket,
    #     name=thread_name,
    #     args=(thread_name, socket_url_trade, on_message_trade, on_error, on_close),
    #     daemon=True
    # )
    # trade_thread.start()
    # threads[thread_name] = trade_thread

    # orderbook WebSocket
    thread_name = f'orderbook_{symbol_lower}'
    socket_url_orderbook = f'wss://fstream.binance.com/ws/{symbol_lower}@depth20'
    orderbook_thread = threading.Thread(
        target=run_websocket,
        name=thread_name,
        args=(thread_name, socket_url_orderbook, on_message_orderbook, on_error, on_close),
        daemon=True
    )
    orderbook_thread.start()
    threads[thread_name] = orderbook_thread

    # 1분 타임프레임 WebSocket
    thread_name = f'kline_1m_{symbol_lower}'
    socket_url_1m = f'wss://fstream.binance.com/ws/{symbol_lower}@kline_1m'
    kline_1m_thread = threading.Thread(
        target=run_websocket,
        name=thread_name,
        args=(thread_name, socket_url_1m, on_message_1m, on_error, on_close),
        daemon=True
    )
    kline_1m_thread.start()
    threads[thread_name] = kline_1m_thread

    # 1시간 타임프레임 WebSocket
    thread_name = f'kline_1h_{symbol_lower}'
    socket_url_1h = f'wss://fstream.binance.com/ws/{symbol_lower}@kline_1h'
    kline_1h_thread = threading.Thread(
        target=run_websocket,
        name=thread_name,
        args=(thread_name, socket_url_1h, on_message_1h, on_error, on_close),
        daemon=True
    )
    kline_1h_thread.start()
    threads[thread_name] = kline_1h_thread

# def start_websocket(symbol_lower):
#     def run_websocket(socket_url, on_message, on_error, on_close):
#         while True:
#             try:
#                 ws = websocket.WebSocketApp(
#                     socket_url,
#                     on_message=on_message,
#                     on_error=on_error,
#                     on_close=on_close
#                 )
#                 ws.run_forever()
#                 # time.sleep(1)
#             except Exception as e:
#                 print(f"WebSocket Error for {socket_url}: {e}")
#                 time.sleep(5)  # 재시작 전에 잠시 대기

#     # 실시간 거래 데이터(WebSocket) 실행
#     thread_name = f'aggTrade_{symbol_lower}'
#     socket_url_trade = f'wss://fstream.binance.com/ws/{symbol_lower}@aggTrade'
#     trade_thread = threading.Thread(target=run_websocket, name=thread_name, args=(socket_url_trade, on_message_trade, on_error, on_close), daemon=True)
#     trade_thread.start()
#     threads[thread_name] = trade_thread

#     # orderbook WebSocket
#     thread_name = f'orderbook_{symbol_lower}'
#     socket_url_orderbook = f'wss://fstream.binance.com/ws/{symbol_lower}@depth20'
#     orderbook_thread = threading.Thread(target=run_websocket, name=thread_name, args=(socket_url_orderbook, on_message_orderbook, on_error, on_close), daemon=True)
#     orderbook_thread.start()
#     threads[thread_name] = orderbook_thread

#     # 1분 타임프레임 WebSocket
#     thread_name = f'kline_1m_{symbol_lower}'
#     socket_url_1m = f'wss://fstream.binance.com/ws/{symbol_lower}@kline_1m'
#     kline_1m_thread = threading.Thread(target=run_websocket, name=thread_name, args=(socket_url_1m, on_message_1m, on_error, on_close), daemon=True)
#     kline_1m_thread.start()
#     threads[thread_name] = kline_1m_thread

#     # 1시간 타임프레임 WebSocket
#     thread_name = f'kline_1h_{symbol_lower}'
#     socket_url_1h = f'wss://fstream.binance.com/ws/{symbol_lower}@kline_1h'
#     kline_1h_thread = threading.Thread(target=run_websocket, name=thread_name, args=(socket_url_1h, on_message_1h, on_error, on_close), daemon=True)
#     kline_1h_thread.start()
#     threads[thread_name] = kline_1h_thread

# def start_websocket(symbol_lower):
#     # orderbook WebSocket
#     socket_url_orderbook = f'wss://fstream.binance.com/ws/{symbol_lower}@depth20'
#     ws_orderbook = websocket.WebSocketApp(
#         socket_url_orderbook, 
#         on_message=on_message_orderbook, 
#         on_error=on_error, 
#         on_close=on_close
#         )
#     threading.Thread(target=ws_orderbook.run_forever).start()
    
#     # 1분 타임프레임 WebSocket
#     socket_url_1m = f'wss://fstream.binance.com/ws/{symbol_lower}@kline_1m'
#     ws_1m = websocket.WebSocketApp(
#         socket_url_1m, 
#         on_message=on_message_1m, 
#         on_error=on_error, 
#         on_close=on_close
#         )
#     threading.Thread(target=ws_1m.run_forever).start()

#     # 1시간 타임프레임 WebSocket
#     socket_url_1h = f'wss://fstream.binance.com/ws/{symbol_lower}@kline_1h'
#     ws_1h = websocket.WebSocketApp(
#         socket_url_1h, 
#         on_message=on_message_1h, 
#         on_error=on_error, 
#         on_close=on_close)
#     threading.Thread(target=ws_1h.run_forever).start()

#     """
#     실시간 거래 데이터(WebSocket) 실행
#     """
#     socket_url_trade = f'wss://fstream.binance.com/ws/{symbol_lower}@aggTrade'
#     ws_trade = websocket.WebSocketApp(
#         socket_url_trade,
#         on_message=on_message_trade,
#         on_error=on_error,
#         on_close=on_close,
#     )
#     threading.Thread(target=ws_trade.run_forever).start()
# websocket_threads = []
# 코인 리스트의 모든 코인에 대해 웹소켓 실행
# def run_websockets():
#     global websocket_threads
#     websocket_threads = []  # 웹소켓 스레드 리스트 초기화
#     start_account_update_websocket()

#     for symbol in COIN_LIST:
#         symbol_lower = symbol.lower()  # 소문자로 변환
#         thread = threading.Thread(target=start_websocket, args=(symbol_lower,), daemon=True)
#         thread.start()
#         websocket_threads.append(thread)  # 스레드 리스트에 추가

#         time.sleep(2)  # 각 연결 사이의 딜레이를 늘려 안정성 확보
    # return thread_name

def run_websockets():
    start_account_update_websocket()
    for symbol in COIN_LIST:
        symbol_lower = symbol.lower()  # 소문자로 변환
        start_websocket(symbol_lower)
        time.sleep(1)  # 각 연결 사이의 딜레이를 늘려 안정성 확보

# run_websockets()  # 웹소켓 일괄 실행


# stop_event = threading.Event()
# def start_websockets():
#     global websocket_threads
#     if websocket_threads:
#         # 기존 스레드를 중지합니다.
#         stop_websockets()
#     # 새로운 스레드를 시작합니다.
#     run_websockets()

# def stop_websockets():
#     global websocket_threads
#     for thread in websocket_threads:
#         if thread.is_alive():
#             # 스레드를 중지하는 로직 (예: 플래그 설정)
#             stop_event.set()
#             thread.join()
#     websocket_threads = []

