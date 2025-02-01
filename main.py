import time
from datetime import datetime
import schedule
import numpy as np
import pandas as pd
from indicators import calculate_mpr, add_indicators,get_tick_size,calculate_poc,tick_size
from database import get_coin_data, coin_data, fetch_agg_trades, get_trade_ratio
from config import binance, nowtime, COIN_LIST,TRADE_RATE,datetime,KST
from timecheck import timecheck
from position_check import position_check, position_data,balance_data
from websocket_manager import run_websockets, position_data_update,orderbook_data
import logging

# 로깅 설정
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
def trade_history(trade):
    with open("Binance_autotrade\\binance_trade_history.txt", "a", encoding="utf-8") as fp:
        fp.write(trade)  # 파일에 잔액 정보 기록
        fp.write('\n')  # 새로운 줄 추가
    return

def longstart(symbol, order_amount, coin_high, reason, indicator):
    try:
        binance.create_order(symbol=symbol,type="LIMIT",side="buy",amount=order_amount,price=coin_high)
        time.sleep(1)
        # TRAILING_STOP_MARKET 주문 생성
        binance.create_order(
            symbol=symbol,
            side="SELL",  # 매도 주문
            type="TRAILING_STOP_MARKET",
            amount=order_amount,
            params={'trailingPercent': 0.5}
            # trailingPercent=2  # 트레일링 비율 (%)
        )
    except Exception as e:
        print(f"{symbol} {e}")
        return
    trade = (
        f"{nowtime}\t{symbol}\t{reason} - 롱포지션 진입\n"
        f"{indicator}\n"
    )
    print(trade)
    trade_history(trade)
    position_check(symbol)   
    return position_data

def shortend(symbol,indicator,position_amount, coin_high,reason):
    open_orders = binance.fetch_open_orders(symbol)
    for order in open_orders:
        print(f"Cancelling open order {order['id']}")
        binance.cancel_order(order['id'], symbol=symbol)
    try:
        binance.create_order(symbol=symbol,type="LIMIT",side="buy",amount=position_amount*-1,price=coin_high)
    except Exception as e:
        print(f"{symbol} {e}")
        return

    trade = (
        f"{nowtime}\t{symbol}\t{reason} - 숏포지션 청산\n"
        f"{indicator}\n"
    )
    print(trade)
    trade_history(trade)

    position_check(symbol)
    return position_data

def shortstart(symbol, indicator, order_amount, coin_low, reason):
    try:
        binance.create_order(symbol=symbol, type="LIMIT", side="sell", amount=order_amount, price=coin_low)
        time.sleep(1)
        # TRAILING_STOP_MARKET 주문 생성
        binance.create_order(
            symbol=symbol,
            side="BUY",  # 매도 주문
            type="TRAILING_STOP_MARKET",
            amount=order_amount,
            params={'trailingPercent': 0.5}
            # trailingPercent=2  # 트레일링 비율 (%)
        )
    except Exception as e:
        print(f"{symbol} {e}")
        return
    trade = (
        f"{nowtime}\t{symbol}\t{reason} - 숏포지션 진입\n"
        f"{indicator}\n"
    )
    print(trade)
    trade_history(trade)
    position_check(symbol)
    return position_data

def longend(symbol,indicator,position_amount, coin_low,reason):
    open_orders = binance.fetch_open_orders(symbol)
    for order in open_orders:
        print(f"Cancelling open order {order['id']}")
        binance.cancel_order(order['id'], symbol=symbol)

    try:
        binance.create_order(symbol=symbol,type="LIMIT",side="sell",amount=position_amount,price=coin_low)
    except Exception as e:
        print(f"{symbol} {e}")
        return
    trade = (
        f"{nowtime}\t{symbol}\t{reason} - 롱포지션 청산\n"
        f"{indicator}\n"
    )
    print(trade)
    trade_history(trade)
    position_check(symbol)
    return position_data

def execute_order(symbol, side, amount, price, reason, indicator):
    """주문 실행 공통 함수"""
    try:
        # 기본 LIMIT 주문
        binance.create_order(
            symbol=symbol,
            type="LIMIT",
            side=side,
            amount=amount,
            price=price
        )
        
        # 트레일링 스탑 주문
        time.sleep(1)
        binance.create_order(
            symbol=symbol,
            side="SELL" if side == "buy" else "BUY",
            type="TRAILING_STOP_MARKET",
            amount=amount,
            params={'trailingPercent': 0.5}
        )
        
        # 거래 기록
        trade_msg = f"{nowtime}\t{symbol}\t{reason} - {'롱' if side == 'buy' else '숏'} 포지션 진입\n{indicator}"
        print(trade_msg)
        trade_history(trade_msg)
        position_check(symbol)

    except Exception as e:
        print(f"{symbol} 주문 실패: {e}")

def determine_market_status(df):
    """ADX 기반 추세 강도 판단 (개선 버전)"""
    try:
        # 1. 신호선 0 체크
        signal_line = df['Signal_Line'].iloc[-1]
        if signal_line == 0:
            macd_signal_rate_hour = 0  # 0으로 나누기 방지
        else:
            macd_diff = abs(df['MACD'].iloc[-1] - signal_line)
            macd_signal_rate_hour = round((macd_diff / signal_line) * 100, 2)

        # 2. 이동평균선 조건
        is_rising_ma = (
            df['SMA_7'].iloc[-1] > df['SMA_15'].iloc[-1] > df['SMA_50'].iloc[-1] and
            df['SMA_7'].iloc[-1] > df['SMA_7'].iloc[-2] and
            df['SMA_15'].iloc[-1] > df['SMA_15'].iloc[-2]
        )
        is_falling_ma = (
            df['SMA_7'].iloc[-1] < df['SMA_15'].iloc[-1] < df['SMA_50'].iloc[-1] and
            df['SMA_7'].iloc[-1] < df['SMA_7'].iloc[-2] and
            df['SMA_15'].iloc[-1] < df['SMA_15'].iloc[-2]
        )

        # 3. MACD 조건
        macd_vals = df['MACD'].tail(3).values
        is_rising_macd = (
            df['MACD'].iloc[-1] > df['Signal_Line'].iloc[-1] and
            macd_vals[-1] > macd_vals[-2] > macd_vals[-3] and
            macd_signal_rate_hour > 10
        )
        is_falling_macd = (
            df['MACD'].iloc[-1] < df['Signal_Line'].iloc[-1] and
            macd_vals[-1] < macd_vals[-2] < macd_vals[-3] and
            macd_signal_rate_hour > 10
        )

        # 4. ADX 기반 추세 판단
        adx_value = df['ADX'].iloc[-1]
        if adx_value > 25:
            if is_rising_ma or is_rising_macd:
                return "Strong_Trend_Up"
            if is_falling_ma or is_falling_macd:
                return "Strong_Trend_Down"
        else:
            if is_rising_ma or is_rising_macd:
                return "Rising"
            if is_falling_ma or is_falling_macd:
                return "Falling"
                
        return "Sideways_Or_Weak_Trend"
        
    except Exception as e:
        print(f"추세 판단 오류: {e}")
        return "Error_State"

# def determine_market_status(df):
#     """ADX 통한 추세 강도 판단"""

#     macd_signal_rate_hour= round(abs((df['MACD'][-1]-df['Signal_Line'][-1])/df['Signal_Line'][-1]*100),2)
#     # 상승장 조건
#     is_rising_ma = df['SMA_7'][-1] > df['SMA_15'][-1] > df['SMA_50'][-1] and df['SMA_7'][-1] > df['SMA_7'][-2] and df['SMA_15'][-1] > df['SMA_15'][-2]
#     is_rising_macd = df['MACD'][-1] > df['Signal_Line'][-1] and df['MACD'][-1] > df['MACD'][-2] > df['MACD'][-3] and macd_signal_rate_hour > 10 

#     # 하락장 조건
#     is_falling_ma = df['SMA_7'][-1] < df['SMA_15'][-1] < df['SMA_50'][-1] and df['SMA_7'][-1] < df['SMA_7'][-2] and df['SMA_15'][-1] < df['SMA_15'][-2]
#     is_falling_macd = df['MACD'][-1] < df['Signal_Line'][-1] and df['MACD'][-1] < df['MACD'][-2] < df['MACD'][-3] and macd_signal_rate_hour > 10 

    
#     if df['ADX'][-1] > 25:
#         if is_rising_ma or is_rising_macd: return "Strong_Trend_Up"
#         if is_falling_ma or is_falling_macd: return "Strong_Trend_Down"
#     if df['ADX'][-1] < 25:
#         if is_rising_ma or is_rising_macd: return "Rising"
#         if is_falling_ma or is_falling_macd: return "Falling"
#     return "Sideways_Or_Weak_Trend"

def check_scalping_condition(df, market_status):
    """추세 필터 통합 스캘핑 조건"""
    current = df.iloc[-1]
    volume_condition = current['Volume'] > df['Volume'].rolling(20).mean()[-1]
    
    long_cond = (
        market_status in ["Strong_Trend_Up", "Rising"] and
        current['stochastic_signal'] == '매수' and
        current['Close'] <= current['Lower_Band'] * 0.998 and
        volume_condition
    )
    
    short_cond = (
        market_status in ["Strong_Trend_Down", "Falling"] and
        current['stochastic_signal'] == '매도' and
        current['Close'] >= current['Upper_Band'] * 1.002 and
        volume_condition
    )
    
    return "long" if long_cond else "short" if short_cond else None

# def check_scalping_condition(df_minute):
#     """스캘핑 매매 조건을 확인합니다."""

#     current_price = df_minute['Close'].iloc[-1]
#     channel_high = df_minute['channel_high'].iloc[-1]
#     channel_low = df_minute['channel_low'].iloc[-1]
#     upper_band = df_minute['Upper_Band'].iloc[-1]
#     lower_band = df_minute['Lower_Band'].iloc[-1]
#     stochastic_signal = df_minute['stochastic_signal'].iloc[-1]

#     # 상방 추세에서 매수 조건
#     if (stochastic_signal == '매수' and
#         current_price <= channel_low and
#         current_price <= lower_band):
#        return "long"

#     # 하방 추세에서 매도 조건
#     if (stochastic_signal == '매도' and
#         current_price >= channel_high and
#         current_price >= upper_band):
#         return "short"

#     return None

def main():
    try:
        schedule.every(1).hour.at("01:01").do(timecheck)
        timecheck()
        position_check()
        get_coin_data()
        time.sleep(5)
        run_websockets()  # 웹소켓 일괄 실행
        # start_account_update_websocket()  # ACCOUNT_UPDATE 웹소켓 실행
        get_tick_size()    

        print('COIN_LIST:',COIN_LIST)
        while True:
            for symbol in COIN_LIST:
                nowtime = datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')
                # 각 데이터프레임 가져오기
                order_book = orderbook_data[symbol]
                df_minute = coin_data[symbol]['1m']
                df_hour = coin_data[symbol]['1h']

                # 1분 및 3분 데이터에 각각 지표 추가
                df_minute = add_indicators(df_minute)
                df_hour = add_indicators(df_hour)
                print(df_minute)
                # 시장 상태 분석
                market_status = determine_market_status(df_hour)
                print(f"{symbol} 시장 상태: {market_status}")
                # 시간 데이터 분석
                # macd_hour = np.array(df_hour["MACD"])
                # macd_signal_hour = np.array(df_hour["Signal_Line"])
                # macd_signal_rate_hour= round(abs((macd_hour[-1]-macd_signal_hour[-1])/macd_signal_hour[-1]*100),2)
                # sma_7 = np.array(df_hour["SMA_7"])
                # sma_15 = np.array(df_hour["SMA_15"])
                # sma_50 = np.array(df_hour["SMA_50"])

                # # 상승장 조건
                # is_rising_ma = sma_7[-1] > sma_15[-1] > sma_50[-1] and sma_7[-1] > sma_7[-2] and sma_15[-1] > sma_15[-2]
                # is_rising_macd = macd_hour[-1] > macd_signal_hour[-1] and macd_hour[-1] > macd_hour[-2] > macd_hour[-3] and macd_signal_rate_hour > 10 

                # # 하락장 조건
                # is_falling_ma = sma_7[-1] < sma_15[-1] < sma_50[-1] and sma_7[-1] < sma_7[-2] and sma_15[-1] < sma_15[-2]
                # is_falling_macd = macd_hour[-1] < macd_signal_hour[-1] and macd_hour[-1] < macd_hour[-2] < macd_hour[-3] and macd_signal_rate_hour > 10 

                # # 시장 상태 결정
                # if is_rising_ma or is_rising_macd:
                #     market_status = "Rising"
                # elif is_falling_ma or is_falling_macd:
                #     market_status = "Falling"
                # else:
                #     market_status = "Sideways"
                    
                # Market Pressure Ratio (상위 10개 레벨)
                mpr,coin_low,coin_high = calculate_mpr(order_book, levels=20)
                print("Market Pressure Ratio (상위 10개 레벨):", mpr)

                trade_ratio = fetch_agg_trades(symbol)
                print("Trade Ratio:", trade_ratio)
                # VP Box Indicator의 POC
                # poc = calculate_poc(df_minute)
                # print('poc:',poc)

                # ticksize = tick_size[symbol]
                # print('ticksize:',ticksize)

                # 1분 데이터 분석
                rsi = np.array(df_minute["RSI_14"])
                rsi_now = round(rsi[-1],3) 
                rsi_min = round(df_minute["RSI_14"].tail(5).min(),3)
                rsi_max = round(df_minute["RSI_14"].tail(5).max(),3)
                cur_rsi = round(df_minute["RSI_14"].iloc[-1],3)
                
                macd = np.array(df_minute["MACD"])
                macdhist = np.array(df_minute["MACD_Histogram"])
                macd_signal = np.array(df_minute["Signal_Line"])
                macd_mean = sum(macd[-7:]) / 5  # 최근 5일의 MACD 평균
                macd_max = macd.max()  
                macd_max5 = macd[-5:].max()  
                macd_min = macd.min()  
                macd_min7 = macd[-7:].min()  

                open_data = np.array(df_minute["Open"])
                close_data = np.array(df_minute["Close"])
                high_data = np.array(df_minute["High"])
                low_data = np.array(df_minute["Low"])
                high_max = high_data.max()  
                high_max5 = high_data[-5:].max()  
                low_min = low_data.min()  
                low_min5 = low_data[-5:].min()  
                cur_price = close_data[-1]
                high_sell_point = 100 * (high_data[-1] - cur_price) / high_data[-1]  # Calculate high_sell_point
                low_sell_point = 100 * (low_data[-1] - cur_price) / low_data[-1]    # Calculate low_sell_point
                upraise =round((cur_price-open_data[-1])/open_data[-1]*100,2)
                pre_upraise = round((close_data[-2] - open_data[-2]) / open_data[-2] * 100, 2)

                if macd_signal[-1] != 0 and not np.isnan(macd_signal[-1]):
                    macd_signal_rate= round(abs((macd[-1]-macd_signal[-1])/macd_signal[-1]*100),2)
                else:
                    macd_signal_rate = 0
                # scalping_signal = check_scalping_condition(df_minute)

                # rising_market = (
                #     macd[-1] > macd_signal[-1] and
                #     macd[-2] > macd_signal[-2] and
                #     macd[-1] >= macd[-2] > macd[-3] and
                #     abs(macd[-1] - macd_signal[-1]) > 0.5 and  # MACD와 시그널 간의 차이
                #     short_ma[-1] > long_ma[-1] and  # 단기/장기 이동평균선 비교
                #     volume[-1] > sum(volume[-20:]) / 20  # 거래량 확인
                # )

                # falling_market = (
                #     macd[-1] < macd_signal[-1] and
                #     macd[-2] < macd_signal[-2] and
                #     macd[-1] <= macd[-2] < macd[-3] and
                #     abs(macd[-1] - macd_signal[-1]) > 0.5 and  # MACD와 시그널 간의 차이
                #     short_ma[-1] < long_ma[-1] and  # 단기/장기 이동평균선 비교
                #     volume[-1] > sum(volume[-20:]) / 20  # 거래량 확인
                # )

                # MACD 상승 추세 전환 (Upward Change)
                macd_up_change = (
                    macd[-1] > macd[-2]  # 최근 1일이 2일보다 크면 상승
                    and macd[-2] >= macd[-3]  # 최근 2일도 3일보다 크면 상승 추세 지속
                    and macd[-3] <= macd[-4]  # 이전 3일보다 작은 값이었음을 확인 (하락에서 전환)
                    and macd[-4] < macd[-5]  # 이전 3일보다 작은 값이었음을 확인 (하락에서 전환)
                    and macd[-1] < macd_mean
                    and macdhist[-1] < 0  # 양의 영역으로 진입했을 때 상승 신호
                    # and macd_signal_rate > 10  # MACD와 Signal Line의 차이가 10% 이상
                )
                # MACD 하락 추세 전환 (Downward Change)
                macd_down_change = (
                    macd[-1] < macd[-2]  # 최근 1일이 2일보다 작으면 하락
                    and macd[-2] <= macd[-3]  # 최근 2일도 3일보다 작으면 하락 추세 지속
                    and macd[-3] >= macd[-4]  # 이전 3일보다 큰 값이었음을 확인 (상승에서 전환)
                    and macd[-4] > macd[-5]  # 이전 3일보다 큰 값이었음을 확인 (상승에서 전환)
                    and macd[-1] > macd_mean
                    and macdhist[-1] > 0  # 음의 영역으로 진입했을 때 하락 신호
                    # and macd_signal_rate > 10  # MACD와 Signal Line의 차이가 10% 이상
                )
                # MACD 골든크로스 조건
                macd_golden_cross = (
                    macdhist[-1] > macdhist[-2] > macdhist[-3]  # 최근 3일 동안 히스토그램이 상승 중
                    and macdhist[-4:-1].mean() < 0  # 최근 5일 평균이 음수, 하락세에서 전환
                    and (macdhist[-1] > 0 or macdhist[-2] > 0)  # 양의 영역으로 전환됨
                    and macd_signal_rate > 10  # MACD와 Signal Line의 차이가 10% 이상
                )
                # MACD 데드크로스 조건
                macd_dead_cross = (
                    macdhist[-1] < macdhist[-2] < macdhist[-3]  # 최근 3일 동안 히스토그램이 하락 중
                    and macdhist[-4:-1].mean() > 0  # 최근 5일 평균이 양수, 상승세에서 전환
                    and (macdhist[-1] < 0 or macdhist[-2] < 0)  # 음의 영역으로 진입
                    and macd_signal_rate > 10  # MACD와 Signal Line의 차이가 10% 이상
                )

                # balance check
                total_wallet_balance = balance_data['wallet']
                usdt_free = balance_data['free']

                # position check
                avg_price = position_data[symbol]['avg_price']
                position_amount = position_data[symbol]['position_amount']
                leverage = position_data[symbol]['leverage']
                unrealizedProfit = position_data[symbol]['unrealizedProfit']
                breakeven_price = position_data[symbol]['breakeven_price']

                order_balance = round(total_wallet_balance * TRADE_RATE * leverage,2) # 매매 실행시 금액 usdt 
                order_amount = round(order_balance / cur_price,2) # 매수 실행시 매수량으로 사용(코인수량)
                balance_amount = round(avg_price*abs(position_amount)+unrealizedProfit,2) # 보유 코인의 현 평가금액

                # if avg_price != 0 :
                #     if position_amount < 0 : 
                #         mygain = round(100*(cur_price-avg_price)*leverage/avg_price*-1,2)
                #     elif position_amount > 0 :
                #         mygain = round(100*(cur_price-avg_price)*leverage/avg_price,2)
                # else:
                #     mygain = 0

                if avg_price != 0:
                    if position_amount == 0:
                        mygain = 0  # position_amount가 0이면 mygain은 0
                    elif position_amount < 0:
                        mygain = round(100 * (cur_price - avg_price) * leverage / avg_price * -1, 2)
                    elif position_amount > 0:
                        mygain = round(100 * (cur_price - avg_price) * leverage / avg_price, 2)
                    else:
                        mygain = 0  # 추가된 else문으로 혹시 모를 오류 방지
                else:
                    mygain = 0  # avg_price가 0이면 mygain은 0

                open_condition = usdt_free > order_balance/leverage*1.1 and (avg_price == 0 or (mygain < -1  and order_balance > balance_amount ))
                close_condition = avg_price != 0 and (mygain > 0.2 or mygain < -1)
                raise_condition = abs(pre_upraise) < 0.4 and abs(upraise) <= 0.3
                indicator = (
                            f"market_status : {market_status}, "
                            f"rsi : {rsi_now}, "
                            f"rsi_min : {rsi_min}, "
                            f"rsi_max : {rsi_max}, "
                            f"macd_signal_rate : {macd_signal_rate}\n"
                            f"pre_upraise : {pre_upraise}, "
                            f"upraise : {upraise}, "
                            # f"POC : {poc}, "
                            f"MPR : {mpr}, "
                            f"trade_ratio : {trade_ratio}, "
                            f"mygain : {mygain}"
                            )
                # 개선된 스캘핑 조건 확인
                scalping_signal = check_scalping_condition(df_minute, market_status)
                
                # 스캘핑 조건 확인
                # current_price = df_minute['Close'].iloc[-1]
                # channel_high = df_minute['channel_high'].iloc[-1]
                # channel_low = df_minute['channel_low'].iloc[-1]
                # upper_band = df_minute['Upper_Band'].iloc[-1]
                # lower_band = df_minute['Lower_Band'].iloc[-1]
                # stochastic_signal = df_minute['stochastic_signal'].iloc[-1]
                
                # scalping_long_condition = (
                #     stochastic_signal == '매수' and
                #     current_price <= channel_low and
                #     current_price <= lower_band
                # )
                
                # scalping_short_condition = (
                #     stochastic_signal == '매도' and
                #     current_price >= channel_high and
                #     current_price >= upper_band
                # )


                # 거래 조건 확인
                if rsi_now <= 15 and low_sell_point < -0.3 :
                    print(nowtime,symbol,'\n',indicator,'\n')
                    if open_condition :
                        reason = "급락시 롱 진입"
                        longstart(symbol, indicator, order_amount, coin_high, reason)
                    elif position_amount < 0 :
                        reason = "급락시 숏 청산"
                        shortend(symbol,indicator,position_amount, coin_high,reason)
                        continue

                elif rsi_now >= 85 and high_sell_point > 0.3  :
                    print(nowtime,symbol,'\n',indicator,'\n')
                    if open_condition :
                        reason = "급등 후 하락 숏 진입"
                        shortstart(symbol, indicator, order_amount, coin_low, reason)
                    elif position_amount > 0 :
                        reason = "급등 후 하락 롱 청산"
                        longend(symbol,indicator,position_amount, coin_low,reason)
                        continue

                elif macd_up_change and (open_condition or close_condition):
                    print(
                        nowtime, symbol, 'macd_up_change', macd_up_change,
                        'market_status', market_status, '\n', indicator, '\n'
                    )

                    # MACD 상승 롱 진입 조건 (하락장)
                    if (
                        (avg_price == 0 or position_amount > 0) and 
                        raise_condition and (mpr > 0.55 or trade_ratio > 0.55)
                    ):
                        if rsi_now < 50 and rsi_min < 30:
                            reason = "MACD 상승 롱 진입 (하락장)"
                            longstart(symbol, indicator, order_amount, coin_high, reason)

                        # MACD 상승 롱 진입 조건 (상승장)
                        elif market_status == 'Rising' and rsi_now < 55 and rsi_min < 35:
                            order_amount *= 0.5
                            reason = "MACD 상승 롱 진입 (상승장)"
                            longstart(symbol, indicator, order_amount, coin_high, reason)

                    # MACD 상승 숏 청산 조건
                    elif position_amount < 0 and (mpr > 0.55 or trade_ratio > 0.55):
                        reason = "MACD 상승 숏 청산"
                        shortend(symbol, indicator, position_amount, coin_high, reason)
                        continue
                    
                elif macd_down_change and (open_condition or close_condition):
                    print(
                        nowtime, symbol, 'macd_down_change', macd_down_change, 
                        'market_status', market_status, '\n', indicator, '\n'
                    )

                    # MACD 하락 숏 진입 조건 (상승장)
                    if (
                        (avg_price == 0 or position_amount < 0) and 
                        raise_condition and (mpr < 0.45 or trade_ratio < 0.45)
                    ):
                        if rsi_now > 50 and rsi_max > 70:
                            reason = "MACD 하락 숏 진입 (상승장)"
                            shortstart(symbol, indicator, order_amount, coin_low, reason)

                        # MACD 하락 숏 진입 조건 (하락장)
                        elif market_status == 'Falling' and rsi_now > 45 and rsi_max > 60:
                            order_amount *= 0.5
                            reason = "MACD 하락 숏 진입 (하락장)"
                            shortstart(symbol, indicator, order_amount, coin_low, reason)

                    # MACD 하락 롱 청산 조건
                    elif position_amount > 0 and (mpr < 0.45 or trade_ratio < 0.45):
                        reason = "MACD 하락 롱 청산"
                        longend(symbol, indicator, position_amount, coin_low, reason)
                        continue

                # elif scalping_long_condition :
                #     print(nowtime,symbol,'scalping_long_condition',scalping_long_condition,'\n',indicator,'\n')
                #     if open_condition and raise_condition:
                #         reason = "스캘핑 롱 진입"
                #         longstart(symbol, indicator, order_amount, coin_high, reason)
                #     continue

                # elif scalping_short_condition:
                #     print(nowtime,symbol,'scalping_short_condition',scalping_short_condition,'\n',indicator,'\n')
                #     if open_condition and raise_condition:
                #         reason = "스캘핑 숏 진입"
                #         shortstart(symbol, indicator, order_amount, coin_low, reason)
                #     continue
                elif scalping_signal == "long" and open_condition:
                    execute_order(
                        symbol=symbol,
                        side="buy",
                        amount=order_amount,
                        price=coin_high,
                        reason="개선된 스캘핑 롱 진입",
                        indicator=indicator
                    )
                    
                elif scalping_signal == "short" and open_condition:
                    execute_order(
                        symbol=symbol,
                        side="sell",
                        amount=order_amount,
                        price=coin_low,
                        reason="개선된 스캘핑 숏 진입",
                        indicator=indicator
                    )
                elif macd_golden_cross  and close_condition and position_amount < 0  and (mpr > 0.55 or trade_ratio > 0.55) :
                    print(nowtime,symbol,'macd_golden_cross',macd_golden_cross,'\n',indicator,'\n')
                    reason = "MACD 골든크로스 숏 청산"
                    shortend(symbol,indicator,position_amount, coin_high,reason)
                    continue 

                elif macd_dead_cross  and close_condition and position_amount > 0 and (mpr < 0.45 or trade_ratio < 0.45) :
                    print(nowtime,symbol,'macd_dead_cross',macd_dead_cross,'\n',indicator,'\n')
                    reason = "MACD 데드크로스 롱 청산"
                    longend(symbol,indicator,position_amount, coin_low,reason)
                    continue 
                elif macdhist[-1] <=0 and macdhist[-3] >= macdhist[-2] > macdhist[-1] :
                    if  position_amount > 0 and mygain < -5 :
                        reason = "배드포지션 롱 손절"
                        longend(symbol,indicator,position_amount, coin_low,reason)
                        continue 
                elif macdhist[-1] >=0 and macdhist[-3] <= macdhist[-2] < macdhist[-1] :
                    if position_amount < 0 and mygain < -5 :
                        reason = "배드포지션 솟 손절"
                        shortend(symbol,indicator,position_amount, coin_high,reason)

                schedule.run_pending()
                time.sleep(1)
    except Exception as e:
        logging.error(f"프로그램 실행 중 오류 발생: {e}")
    except KeyboardInterrupt:
        print("프로그램이 종료되었습니다.")

if __name__ == "__main__":
    main()

