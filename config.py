import os
from datetime import timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

# API 설정
API_KEY = os.getenv("BINANCE_API_KEY")
SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 거래 설정
# COIN_LIST = ['XRPUSDT','WIFUSDT']
COIN_LIST = ['XRPUSDT','HBARUSDT','ADAUSDT','WIFUSDT']
TRADE_RATE = 0.2
TARGET_LEVERAGE = 5
INTERVAL = "1m"
KST = timezone(timedelta(hours=9))
BASE_URL = "https://fapi.binance.com"

# 현재 디렉토리 기준으로 상대 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, 'logs')

# 파일 경로
BALANCE_LOG = os.path.join(LOG_DIR, "balance_log.txt")
TRADE_LOG = os.path.join(LOG_DIR, "trade_log.txt")
PROGRAM_LOG = os.path.join(LOG_DIR, "program_log.txt")
DATA_DIR = "my_bot/data"
# BALANCE_LOG = "my_bot/logs/balance/balance_log.txt"
# TRADE_LOG = "my_bot/logs/trade/trade_log.txt"
# PROGRAM_LOG = "my_bot/logs/program/program_log.txt"
