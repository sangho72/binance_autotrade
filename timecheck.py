import subprocess
import time
from config import nowtime,client,binance

# 시간 동기화 함수
def sync_time():
    try:
        # 시간 동기화 실행 명령어 (vscode를 관리자모드로 실행해야됨)
        command = "w32tm /resync"

        # 명령어 실행 
        subprocess.run(command, check=True, shell=True)

        print("시간 동기화가 완료되었습니다.")
    except Exception as e:
        print(f"에러 발생: {e}")
    return

def timecheck():
    # nowtime = datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')
    time_diff = int(time.time() * 1000) - client.get_server_time()['serverTime']
    print(nowtime, "\t", time_diff, "\t")
    if abs(time_diff) > 500:
        sync_time()
    return

# timecheck()
# symbol = "WIFUSDT"
# order_amount = 5
# coin_low = 1.4995

# def shortstart1(symbol, order_amount, coin_low):
#     try:
#         binance.create_order(symbol=symbol, type="LIMIT", side="sell", amount=order_amount, price=coin_low)
#         # TRAILING_STOP_MARKET 주문 생성
#         binance.create_order(
#             symbol=symbol,
#             side="BUY",  # 매도 주문
#             type="TRAILING_STOP_MARKET",
#             amount=order_amount,
#             params={'trailingPercent': 2}
#             # trailingPercent=2  # 트레일링 비율 (%)
#         )
#     except Exception as e:
#         print(f"{symbol} {e}")
#         return
# shortstart1(symbol, order_amount, coin_low)