import time
import hmac
import hashlib
import requests
from datetime import datetime, timezone, timedelta
from config import BINANCE_API_KEY, BINANCE_SECRET_KEY, umfuture,TARGET_LEVERAGE , COIN_LIST, nowtime

def write_balance(binance_balance):
    with open("Binance_autotrade\\binance_balance.txt", "a") as fp :
        fp.write(binance_balance)
        fp.write('\n')

def get_account_info():
    base_url = "https://fapi.binance.com"
    endpoint = "/fapi/v2/account"
    url = base_url + endpoint

    # 타임스탬프와 서명 생성
    timestamp = int(time.time() * 1000)
    query_string = f"timestamp={timestamp}"
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
    response = requests.get(url, headers=headers, params={"timestamp": timestamp, "signature": signature})

    # 결과 반환
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": response.status_code, "message": response.text}
 
    
# position_data 정의
position_data = {symbol: {"avg_price": 0.0, "position_amount": 0.0, "leverage": 0, "unrealizedProfit": 0.0, "breakeven_price": 0.0} for symbol in COIN_LIST}
total_wallet_balance = 0.0
usdt_free = 0.0
balance_data = {"wallet": 0.0, "total": 0.0, "free": 0, "used": 0.0, "PNL": 0.0} 
def balance_check(event_reason=None):
    nowtime = datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S')
    balance = get_account_info()
    # print(balance)
    total_wallet_balance = round(float(balance['totalWalletBalance']),3) # total wallet balance, only for USDT asset
    total_unrealized_profit = round(float(balance['totalUnrealizedProfit']),3)
    usdt_free = round(float(balance['availableBalance']),3) # usdt_free
    usdt_used = round(float(balance['totalInitialMargin']),3) # usdt_used
    usdt_total = round(float(balance['totalMarginBalance']),3) # usdt_total

    balance_data['wallet']=total_wallet_balance
    balance_data['total']=usdt_total
    balance_data['free']=usdt_free
    balance_data['used']=usdt_used
    balance_data['PNL']=total_unrealized_profit

    binance_balance = (
                    f"{nowtime}\t"
                    f"wallet: {total_wallet_balance}\t"
                    f"total: {usdt_total}\t"
                    f"free: {usdt_free}\t"
                    f"used: {usdt_used}\t"
                    f"PNL: {total_unrealized_profit}"
                    )
    # event_reason이 전달된 경우, 추가
    if event_reason:
        binance_balance += f"\t{event_reason}"
    print(binance_balance)
    write_balance(binance_balance) # write balance to file
    return balance_data


def position_check(event_reason=None):
    global total_wallet_balance,usdt_free,position_data
    nowtime = datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S')
    balance = get_account_info()
    # print(balance)
    total_wallet_balance = round(float(balance['totalWalletBalance']),3) # total wallet balance, only for USDT asset
    total_unrealized_profit = round(float(balance['totalUnrealizedProfit']),3)
    usdt_free = round(float(balance['availableBalance']),3) # usdt_free
    usdt_used = round(float(balance['totalInitialMargin']),3) # usdt_used
    usdt_total = round(float(balance['totalMarginBalance']),3) # usdt_total

    balance_data['wallet']=total_wallet_balance
    balance_data['total']=usdt_total
    balance_data['free']=usdt_free
    balance_data['used']=usdt_used
    balance_data['PNL']=total_unrealized_profit

    binance_balance = (
                    f"{nowtime}\t"
                    f"wallet: {total_wallet_balance}\t"
                    f"total: {usdt_total}\t"
                    f"free: {usdt_free}\t"
                    f"used: {usdt_used}\t"
                    f"PNL: {total_unrealized_profit}"
                    )
    # event_reason이 전달된 경우, 추가
    if event_reason:
        # binance_balance += f"\tEvent Reason: {event_reason}"
        binance_balance += f"\t{event_reason}"
    print(binance_balance)
    write_balance(binance_balance) # write balance to file

    # position check
    positions = balance['positions']

    for symbol in COIN_LIST:
        for position in positions:
            if position["symbol"] == symbol:
                avg_price = float(position['entryPrice'])
                position_amount = float(position['positionAmt'])
                leverage = float(position['leverage'])
                unrealized_profit = float(position['unrealizedProfit'])
                breakeven_price = float(position['breakEvenPrice'])

                # 포지션 데이터를 저장
                position_data[symbol]['avg_price']=avg_price
                position_data[symbol]['position_amount']=position_amount
                position_data[symbol]['leverage']=leverage
                position_data[symbol]['unrealizedProfit']=unrealized_profit
                position_data[symbol]['breakeven_price']=breakeven_price
                # print(f"Updated position: {symbol}, Data: {position_data[symbol]}")
                # print(symbol,position_data[symbol])

                # 현재 레버리지가 목표 레버리지와 다르면 변경
                try:
                    if int(leverage) != TARGET_LEVERAGE:
                        # 레버리지 변경 요청
                        response = umfuture.change_leverage(symbol=symbol,leverage=TARGET_LEVERAGE)
                        print(f"{symbol} 레버리지 변경 요청 결과: {response}")
                except Exception as e:
                    print(f"{symbol} 레버리지 변경 요청 중 에러 발생: {e}")
    return position_data,balance_data

# position_check()
# print(position_data)


