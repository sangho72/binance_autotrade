import os
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
import ccxt
from binance.um_futures import UMFutures
from binance.client import Client

load_dotenv()

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")

# UTC+9 시간대를 정의
KST = timezone(timedelta(hours=9))
nowtime = datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')

# 상수 정의
INTERVAL = "1m"
COIN_LIST = ['XRPUSDT', 'DOGEUSDT', 'HBARUSDT', 'ADAUSDT','WIFUSDT']
# COIN_LIST = ['XRPUSDT', 'DOGEUSDT', 'HBARUSDT', 'ADAUSDT','WIFUSDT',XLMUSDT']
TRADE_RATE = 0.2  # 거래원하는 비율 - 10%
TARGET_LEVERAGE = 5

binance = ccxt.binance(config={
    'apiKey': BINANCE_API_KEY,
    'secret': BINANCE_SECRET_KEY,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future'
    }
})

client = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY)
umfuture = UMFutures(key=BINANCE_API_KEY, secret=BINANCE_SECRET_KEY)
