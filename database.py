import os
import sqlite3
import pandas as pd
from config import COIN_LIST,client,umfuture
import numpy as np
import pandas_ta as ta
from datetime import datetime, timedelta
from indicators import add_indicators

# 데이터베이스 파일 경로 설정
db_path = os.path.join(os.getcwd(), 'Binance_autotrade', 'coin_data.db')

# SQLite 데이터베이스 연결
# conn = sqlite3.connect(db_path, check_same_thread=False)

def get_db_connection():
    return sqlite3.connect(db_path, check_same_thread=False)

def initialize_database():
    # 데이터베이스 파일이 이미 존재하면 삭제
    if os.path.exists(db_path):
        os.remove(db_path)
    # SQLite 데이터베이스 연결
    global conn
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.close()
    print(f"Initialized database at {db_path}")

def save_coin_data_to_db(symbol, interval, df):
    try:
        conn = get_db_connection()
        table_name = f"coin_data_{symbol}_{interval}"
        df.to_sql(table_name, conn, if_exists='replace', index=False)
        conn.close()
    except Exception as e:
        print(f"Error saving {symbol} {interval} data to database: {e}")

# coin_data 변수 초기화
coin_data = {symbol: [] for symbol in COIN_LIST}

# 초기 데이터 쿼리 함수
def get_symbol_coin_data(symbol):
    # 1분 데이터 가져오기
    historical_data_minute = client.futures_klines(symbol=symbol, interval="1m", limit=999)
    df_minute = pd.DataFrame(historical_data_minute, columns=[
        'Open time', 'Open', 'High', 'Low', 'Close', 'Volume', 
        'Close time', 'Quote asset volume', 'Number of trades', 
        'Taker buy base asset volume', 'Taker buy quote asset volume', 'Ignore'
    ])
    df_minute = df_minute[['Open time', 'Open', 'High', 'Low', 'Close', 'Volume']]
    df_minute['Open time'] = pd.to_datetime(df_minute['Open time'], unit='ms')
    df_minute['Open time'] += pd.Timedelta(hours=9)
    df_minute['Open time'] = df_minute['Open time'].dt.strftime('%Y-%m-%d %H:%M')

    # 각 컬럼의 데이터 형식을 숫자로 변환
    df_minute['Open'] = pd.to_numeric(df_minute['Open'], errors='coerce')
    df_minute['High'] = pd.to_numeric(df_minute['High'], errors='coerce')
    df_minute['Low'] = pd.to_numeric(df_minute['Low'], errors='coerce')
    df_minute['Close'] = pd.to_numeric(df_minute['Close'], errors='coerce')
    df_minute['Volume'] = pd.to_numeric(df_minute['Volume'], errors='coerce')

    # 1분 데이터 저장
    save_coin_data_to_db(symbol, '1m', df_minute)

    # 1시간 데이터 가져오기
    historical_data_hour = client.futures_klines(symbol=symbol, interval="1h", limit=999)
    df_hour = pd.DataFrame(historical_data_hour, columns=[
        'Open time', 'Open', 'High', 'Low', 'Close', 'Volume', 
        'Close time', 'Quote asset volume', 'Number of trades', 
        'Taker buy base asset volume', 'Taker buy quote asset volume', 'Ignore'
    ])
    df_hour = df_hour[['Open time', 'Open', 'High', 'Low', 'Close', 'Volume']]
    df_hour['Open time'] = pd.to_datetime(df_hour['Open time'], unit='ms')
    df_hour['Open time'] += pd.Timedelta(hours=9)
    df_hour['Open time'] = df_hour['Open time'].dt.strftime('%Y-%m-%d %H:%M')

    # 각 컬럼의 데이터 형식을 숫자로 변환
    df_hour['Open'] = pd.to_numeric(df_hour['Open'], errors='coerce')
    df_hour['High'] = pd.to_numeric(df_hour['High'], errors='coerce')
    df_hour['Low'] = pd.to_numeric(df_hour['Low'], errors='coerce')
    df_hour['Close'] = pd.to_numeric(df_hour['Close'], errors='coerce')
    df_hour['Volume'] = pd.to_numeric(df_hour['Volume'], errors='coerce')


    # 1시간 데이터 저장
    save_coin_data_to_db(symbol, '1h', df_hour)

    # 이중 딕셔너리 구조로 데이터 저장
    coin_data[symbol] = {
        '1m': df_minute,
        '1h': df_hour
    }
    # print(df_minute.dtypes)

def get_coin_data():
    initialize_database()
    for symbol in COIN_LIST:
        get_symbol_coin_data(symbol)
    return coin_data

# get_coin_data()
# print(coin_data)

# 프로그램 종료 시 데이터베이스 연결 종료
# def close_db_connection():
#     conn.close()
#     print("Database connection closed.")

# # 프로그램 종료 시 호출
# import atexit
# atexit.register(close_db_connection)

# REST API로 aggTrade 데이터 가져오기
trade_data = {}
get_trade_ratio = {}
# def fetch_agg_trades(symbol):
#     try:
        # trades = client.get_aggregate_trades(symbol=symbol, limit=20)  # 최근 10개 거래 조회
#     except Exception as e:
#         print(f"[Error] {symbol} 데이터 가져오기 실패: {e}")

#     if symbol not in trade_data:
#         trade_data[symbol] = pd.DataFrame(columns=["event_time", "price", "is_bid", "volume"])

#     # 각 거래 데이터 처리
#     for trade in trades:
#         price = float(trade["p"])  # 가격
#         is_bid = not trade["m"]  # 매도(m=True) → False, 매수(m=False) → True
#         volume = float(trade["q"])  # 거래량
#         event_time = datetime.fromtimestamp(trade["T"] / 1000)  # 거래 발생 시간 (밀리초 변환)

#         # 새로운 거래 데이터 추가
#         new_trade = pd.DataFrame([[event_time, price, is_bid, volume]], columns=["event_time", "price", "is_bid", "volume"])

#         # 빈 데이터프레임이나 모든 값이 NA인 항목을 제외하고 concat 수행
#         if not new_trade.empty and not new_trade.isna().all().all():
#             trade_data[symbol] = pd.concat([trade_data[symbol], new_trade], ignore_index=True)

#     # 최근 20분 동안의 데이터로 필터링
#     twenty_minutes_ago = datetime.now() - timedelta(minutes=20)
#     trade_data[symbol] = trade_data[symbol][trade_data[symbol]["event_time"] >= twenty_minutes_ago]

#     # 최근 10분 동안의 데이터로 매수/매도 비율 계산
#     ten_minutes_ago = datetime.now() - timedelta(minutes=10)
#     recent_trades = trade_data[symbol][trade_data[symbol]["event_time"] >= ten_minutes_ago]

#     # 매수/매도 비율 계산
#     total_ask_volume = recent_trades[recent_trades["is_bid"] == False]["volume"].sum()
#     total_bid_volume = recent_trades[recent_trades["is_bid"] == True]["volume"].sum()
#     total_volume = total_ask_volume + total_bid_volume

#     if total_volume > 0:
#         get_trade_ratio[symbol] = total_bid_volume / total_volume
#     else:
#         get_trade_ratio[symbol] = 0.5  # 데이터 부족 시 중립값

#     # 데이터프레임을 CSV 파일로 저장
#     trade_data[symbol].to_csv(f"Binance_autotrade\\coin_data\\trade_data_{symbol}.csv", index=False, sep='\t')
#     # print(f"[{symbol}] 매수/매도 비율: {round(get_trade_ratio[symbol], 4)}")
#     return trade_data,get_trade_ratio

def fetch_agg_trades(symbol):
    try:
        # 현재 시간과 10분 전 시간 계산
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=10)

        # Binance Futures의 최근 10분 동안의 데이터 조회
        trades = umfuture.agg_trades(
            symbol=symbol,
            startTime=int(start_time.timestamp() * 1000),  # 밀리초 단위 변환
            endTime=int(end_time.timestamp() * 1000),  # 밀리초 단위 변환
            limit=1000  # 최대 1000개 조회
        )
        # print(f"[Debug] {symbol} 거래 데이터 개수: {len(trades)}")  # 디버그용 출력
    except Exception as e:
        print(f"[Error] {symbol} 데이터 가져오기 실패: {e}")
        return
        
    # trade_data 초기화
    if symbol not in trade_data:
        trade_data[symbol] = pd.DataFrame(columns=["event_time", "price", "is_bid", "volume"])

    # 각 거래 데이터 처리
    for trade in trades:
        price = float(trade["p"])  # 가격
        is_bid = not trade["m"]  # 매도(m=True) → False, 매수(m=False) → True
        volume = float(trade["q"])  # 거래량
        event_time = datetime.fromtimestamp(trade["T"] / 1000)  # 거래 발생 시간 (밀리초 변환)

        # 새로운 거래 데이터 추가
        new_trade = pd.DataFrame([[event_time, price, is_bid, volume]], columns=["event_time", "price", "is_bid", "volume"])

        # 빈 데이터프레임이나 모든 값이 NA인 항목을 제외하고 concat 수행
        # if not new_trade.empty and not new_trade.isna().all(axis=None):
        #     trade_data[symbol] = pd.concat([trade_data[symbol], new_trade], ignore_index=True)
        # if not new_trade.empty and not new_trade.isnull().all().all():
        trade_data[symbol] = pd.concat(
            [trade_data[symbol], new_trade], 
            ignore_index=True
        ).dropna(how='all')  # 모든 값이 NA인 행 제거
    # 최근 10분 동안의 데이터로 매수/매도 비율 계산
    recent_trades = trade_data[symbol]  # 이미 10분 데이터로 필터링됨

    # 매수/매도 비율 계산
    total_ask_volume = recent_trades[recent_trades["is_bid"] == False]["volume"].sum()
    total_bid_volume = recent_trades[recent_trades["is_bid"] == True]["volume"].sum()
    total_volume = total_ask_volume + total_bid_volume

    if total_volume > 0:
        get_trade_ratio[symbol] = total_bid_volume / total_volume
    else:
        get_trade_ratio[symbol] = 0.5  # 데이터 부족 시 중립값

    # 데이터프레임을 CSV 파일로 저장
    trade_data[symbol].to_csv(f"Binance_autotrade\\coin_data\\trade_data_{symbol}.csv", index=False, sep='\t',mode='w')
    # print(f"[{symbol}] 매수/매도 비율: {round(get_trade_ratio[symbol], 4)}")

    # trade_data 출력
    # print(f"[{symbol}] 거래 데이터:")
    # print(trade_data[symbol])

    return round(get_trade_ratio[symbol],3)


# symbol = 'XRPUSDT'
# fetch_agg_trades(symbol)
# print(trade_data)
