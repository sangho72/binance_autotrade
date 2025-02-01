import pandas as pd
import pandas_ta as ta
import numpy as np
from config import client, COIN_LIST

# Market Pressure Ratio (MPR) 계산
def calculate_mpr(order_book, levels=None):
    """
    Market Pressure Ratio (MPR)를 계산합니다.
    :param order_book: DataFrame, 호가창 데이터 (Bid Volume, Ask Volume 포함)
    :param levels: int, 분석에 사용할 가격 레벨 수 (default: 전체 레벨)
    :return: float, Market Pressure Ratio 
    MPR > 0.5: 상승 압력
    MPR < 0.5: 하락 압력
    """
    try:
        # bids와 asks에서 각 레벨별 거래량만 추출
        bids = order_book["b"]
        asks = order_book["a"]

        # 마지막 bid와 ask에서 가격 추출
        coin_low = float(bids[-1][0])  # bids 리스트의 마지막 가격
        coin_high = float(asks[-1][0])  # asks 리스트의 마지막 가격


        # 상위 levels개 레벨만 사용
        if levels is not None:
            bids = bids[:levels]
            asks = asks[:levels]

        # 매수 및 매도 총 거래량 계산
        total_bid_volume = sum(float(bid[1]) for bid in bids)
        total_ask_volume = sum(float(ask[1]) for ask in asks)

        # 매수, 매도 거래량 합이 0인 경우
        if total_bid_volume + total_ask_volume == 0:
            return 0.5

        # MPR 계산
        mpr = total_bid_volume / (total_bid_volume + total_ask_volume)
        return round(mpr, 4),coin_low,coin_high
    except Exception as e:
        print(f"오류 발생: {e}")
        return 0.5

# def calculate_mpr(order_book, levels=None):
#     """
#     Market Pressure Ratio (MPR)를 계산합니다.
#     :param order_book: DataFrame, 호가창 데이터 (Bid Volume, Ask Volume 포함)
#     :param levels: int, 분석에 사용할 가격 레벨 수 (default: 전체 레벨)
#     :return: float, Market Pressure Ratio 
#     MPR > 0.5: 상승 압력
#     MPR < 0.5: 하락 압력
#     """
#     try:
#         # bids와 asks에서 각 레벨별 거래량만 추출
#         bids = order_book["bid_qty"]
#         asks = order_book["ask_qty"]

#         # 마지막 bid와 ask에서 가격 추출
#         coin_low = float(order_book["bid_price"][-1])  # bids 리스트의 마지막 가격
#         coin_high = float(order_book["ask_price"][-1])  # asks 리스트의 마지막 가격

#         # 상위 levels개 레벨만 사용
#         if levels is not None:
#             bids = bids[:levels]
#             asks = asks[:levels]

#         # 매수 및 매도 총 거래량 계산
#         total_bid_volume = sum(float(bid) for bid in bids)
#         total_ask_volume = sum(float(ask) for ask in asks)

#         # 매수, 매도 거래량 합이 0인 경우
#         if total_bid_volume + total_ask_volume == 0:
#             return 0.5

#         # MPR 계산
#         mpr = total_bid_volume / (total_bid_volume + total_ask_volume)

#         return round(mpr, 4),coin_low,coin_high
#     except Exception as e:
#         print(f"오류 발생: {e}")
#         return 0.5

# 호가 단위 가져오기 함수
tick_size = {}
def get_tick_size():
    global tick_size
    info = client.futures_exchange_info()
    for s in info['symbols']:
        if s['symbol'] in COIN_LIST:
            for f in s['filters']:
                if f['filterType'] == 'PRICE_FILTER':
                    tick_size[s['symbol']] = float(f['tickSize'])
    print('tick_size',tick_size)                
    return tick_size
# tick_size = get_tick_size()
# print(tick_size)

# def add_indicators(df):
#     # df['Close'] = pd.to_numeric(df['Close'], errors='coerce')  # 필요 시 활성화
#     close_prices = df['Close']

#     # 이동 평균 추가 (소수점 4자리 제한)
#     df['SMA_7'] = round(close_prices.rolling(window=7).mean(), 4)
#     df['SMA_15'] = round(close_prices.rolling(window=15).mean(), 4)
#     df['SMA_50'] = round(close_prices.rolling(window=50).mean(), 4)

#     # RSI (14기간) 추가 (소수점 4자리 제한)
#     df['RSI_14'] = round(ta.rsi(close_prices, length=14), 4)

#     # MACD 계산 (소수점 4자리 제한)
#     ema_fast = close_prices.ewm(span=12, adjust=False).mean()
#     ema_slow = close_prices.ewm(span=26, adjust=False).mean()
#     df['MACD'] = round(ema_fast - ema_slow, 6)
#     df['Signal_Line'] = round(df['MACD'].ewm(span=9, adjust=False).mean(), 6)
#     df['MACD_Histogram'] = round(df['MACD'] - df['Signal_Line'], 6)

#     # 볼린저 밴드 계산 (소수점 4자리 제한)
#     df['Middle_Band'] = round(close_prices.rolling(window=20).mean(), 4)
#     std_dev = close_prices.rolling(window=20).std()
#     df['Upper_Band'] = round(df['Middle_Band'] + (std_dev * 2), 4)
#     df['Lower_Band'] = round(df['Middle_Band'] - (std_dev * 2), 4)

#     return df.dropna()


def add_indicators(df):
    # df['Close'] = pd.to_numeric(df['Close'], errors='coerce')  # 필요 시 활성화

        # 인덱스 재설정
    df = df.reset_index(drop=True)

    close_prices = df['Close']
    high_prices = df['High']
    low_prices = df['Low']

    # ADX (Average Directional Index) - 추세 강도 측정
    adx_period = 14
    adx = ta.adx(high_prices, low_prices, close_prices, length=adx_period)
    df['ADX'] = round(adx[f'ADX_{adx_period}'], 4)  # ADX 값만 추출
    
    # ATR (Average True Range) - 변동성 측정
    atr_period = 14
    df['ATR'] = round(ta.atr(high_prices, low_prices, close_prices, length=atr_period), 4)

    stoch = ta.stoch(high_prices, low_prices, close_prices, k=10, d=3, smooth_window=4)
    slowk = stoch.iloc[:, 0].reset_index(drop=True)  # 첫 번째 컬럼 (%K)
    slowd = stoch.iloc[:, 1].reset_index(drop=True)  # 두 번째 컬럼 (%D)

    # 신호 계산
    signal = []
    # for i in range(len(df)):
    #     if i == 0 or pd.isna(slowk.iloc[i]) or pd.isna(slowd.iloc[i]) or pd.isna(slowk.iloc[i-1]) or pd.isna(slowd.iloc[i-1]):
    #         signal.append(None)
    #     elif slowk.iloc[i-1] > slowd.iloc[i-1] and slowk.iloc[i] < slowd.iloc[i]:
    #         signal.append('매도')
    #     elif slowk.iloc[i-1] < slowd.iloc[i-1] and slowk.iloc[i] > slowd.iloc[i]:
    #         signal.append('매수')
    #     else:
    #         signal.append(None)

    for i in range(len(df)):
        # 스토캐스틱 지표의 길이가 원본 데이터프레임보다 짧을 수 있으므로, 인덱스 범위를 확인
        if i >= len(slowk) or i >= len(slowd):
            signal.append(None)
            continue

        # i == 0일 때는 이전 값이 없으므로 None 처리
        if i == 0 or pd.isna(slowk.iloc[i]) or pd.isna(slowd.iloc[i]) or pd.isna(slowk.iloc[i-1]) or pd.isna(slowd.iloc[i-1]):
            signal.append(None)
        elif slowk.iloc[i-1] > slowd.iloc[i-1] and slowk.iloc[i] < slowd.iloc[i]:
            signal.append('매도')
        elif slowk.iloc[i-1] < slowd.iloc[i-1] and slowk.iloc[i] > slowd.iloc[i]:
            signal.append('매수')
        else:
            signal.append(None)            
    # 이동 평균 추가 (소수점 4자리 제한)
    df['SMA_7'] = round(close_prices.rolling(window=7).mean(), 4)
    df['SMA_15'] = round(close_prices.rolling(window=15).mean(), 4)
    df['SMA_50'] = round(close_prices.rolling(window=50).mean(), 4)

    # RSI (14기간) 추가 (소수점 4자리 제한)
    df['RSI_14'] = round(ta.rsi(close_prices, length=14), 4)

    # MACD 계산 (소수점 4자리 제한)
    macd = ta.macd(close_prices, fast=12, slow=26, signal=9)
    df['MACD'] = round(macd['MACD_12_26_9'], 6)
    df['Signal_Line'] = round(macd['MACDs_12_26_9'], 6)
    df['MACD_Histogram'] = round(macd['MACDh_12_26_9'], 6)

    # 프라이스 채널 계산 (소수점 4자리 제한)
    period_pc = 25
    df['channel_high'] = round(high_prices.rolling(window=period_pc).max(), 4)
    df['channel_low'] = round(low_prices.rolling(window=period_pc).min(), 4)

    # 볼린저 밴드 계산 (소수점 4자리 제한)
    period_bb = 30
    mult = 1.5
    df['Middle_Band'] = round(close_prices.rolling(window=period_bb).mean(), 4)
    std_dev = close_prices.rolling(window=period_bb).std()
    df['Upper_Band'] = round(df['Middle_Band'] + (std_dev * mult), 4)
    df['Lower_Band'] = round(df['Middle_Band'] - (std_dev * mult), 4)

    # 스토캐스틱 화산 바닥 신호 추가
    df['stochastic_signal'] = signal

    return df.dropna()

# filepath = "Binance_autotrade\\coin_data\\coin_data_ADAUSDT_1h.csv"
# df_minute = pd.read_csv(filepath, sep='\t')
# df_minute = add_indicators(df_minute)
# print(df_minute.tail(10))

# def add_indicators(df):
#     # df['Close'] = pd.to_numeric(df['Close'], errors='coerce')  # 필요 시 활성화
#     close_prices = df['Close']

#     # ADX 계산 추가
#     # df['ADX'] = ta.adx(high=df['High'], low=df['Low'], close=close_prices, length=14)['ADX_14']

#     # 이동 평균 추가
#     df['SMA_7'] = close_prices.rolling(window=7).mean()
#     df['SMA_15'] = close_prices.rolling(window=15).mean()
#     df['SMA_50'] = close_prices.rolling(window=50).mean()

#     # RSI (14기간) 추가
#     df['RSI_14'] = round(ta.rsi(close_prices, length=14), 4)


#     # MACD 계산
#     ema_fast = close_prices.ewm(span=12, adjust=False).mean()
#     ema_slow = close_prices.ewm(span=26, adjust=False).mean()
#     df['MACD'] = ema_fast - ema_slow
#     df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
#     df['MACD_Histogram'] = df['MACD'] - df['Signal_Line']

#     # 볼린저 밴드 계산
#     df['Middle_Band'] = close_prices.rolling(window=20).mean()
#     std_dev = close_prices.rolling(window=20).std()
#     df['Upper_Band'] = df['Middle_Band'] + (std_dev * 2)
#     df['Lower_Band'] = df['Middle_Band'] - (std_dev * 2)

#     return df.dropna()

# POC 계산 함수
def calculate_poc(df):
    close_prices = df['Close']
    price_bins = np.linspace(close_prices.min(), close_prices.max(), 50)
    df = df.copy()  # 원본 데이터프레임의 복사본을 생성하여 작업
    df.loc[:, 'price_bin'] = pd.cut(df['Close'], bins=price_bins, include_lowest=True, right=False)
    volume_profile = df.groupby('price_bin', observed=True)['Volume'].sum()
    poc_bin = volume_profile.idxmax()
    poc = poc_bin.mid if poc_bin is not None else np.nan  # POC는 가장 많은 거래량이 발생한 가격 수준의 중간값
    return poc

