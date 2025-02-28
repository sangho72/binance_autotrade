from flask import Flask, request, jsonify, render_template
from flask_cors import CORS,cross_origin
import os
import json
import subprocess
import psutil
import time
import logging
from logger import logger as custom_logger
import config 
from models import Session, BalanceData, PositionData, CoinData


app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATUS_FILE = os.path.join(BASE_DIR, "bot_status.json")
logger = logging.getLogger(__name__)
def get_bot_status1():
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r") as f:
            status = json.load(f)
            pid = status.get("pid")
            if pid and psutil.pid_exists(pid):
                return {"status": "running", "pid": pid}
            return {"status": "stopped", "pid": None}
    return {"status": "stopped", "pid": None}

def get_bot_status2():
    """현재 봇 상태 확인"""
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r") as f:
            status = json.load(f)
            pid = status.get("pid")
            if pid and psutil.pid_exists(pid):
                # 프로세스가 실제로 실행 중인지 확인
                try:
                    process = psutil.Process(pid)
                    if process.is_running() and process.name() == "python":  # Python 프로세스인지 확인
                        return {"status": "running", "pid": pid}
                except psutil.NoSuchProcess:
                    pass
            # pid가 존재하지만 프로세스가 종료된 경우 상태 초기화
            return {"status": "stopped", "pid": None}
    return {"status": "stopped", "pid": None}

def get_bot_status():
    """현재 봇 상태 확인"""
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r") as f:
            status = json.load(f)
            pid = status.get("pid")
            if pid and psutil.pid_exists(pid):
                try:
                    process = psutil.Process(pid)
                    if process.is_running():
                        # 프로세스 이름 대신 cmdline으로 확인
                        cmdline = process.cmdline()
                        process_name = process.name().lower()
                        # custom_logger.info(f"PID {pid} - Name: {process_name}, Cmdline: {cmdline}")
                        # Python 프로세스인지 확인 (다양한 이름 허용) 및 main.py 실행 여부
                        if any(python in process_name for python in ["python", "python3", "python.exe"]) and \
                           any("main.py" in arg for arg in cmdline):
                            return {"status": "running", "pid": pid}
                        else:
                            custom_logger.warning(f"PID {pid} exists but not a valid TradingBot process: {cmdline}")
                    else:
                        custom_logger.warning(f"PID {pid} is not running")
                except psutil.NoSuchProcess:
                    custom_logger.warning(f"PID {pid} no longer exists")
            else:
                custom_logger.info(f"PID {pid} not found or invalid")
            # PID가 유효하지 않거나 조건에 맞지 않으면 stopped로 설정
            return {"status": "stopped", "pid": None}
    custom_logger.info("Status file not found")
    return {"status": "stopped", "pid": None}

def update_bot_status(status):
    """상태 파일 업데이트"""
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/status', methods=['GET'])
def status():
    status = get_bot_status()
    print(status)
    return jsonify(status)
@app.route('/start', methods=['POST'])
def start_bot():
    status = get_bot_status()
    if status["status"] == "running":
        custom_logger.info("Bot is already running, skipping start.")
        return jsonify({"status": "success", "message": "Bot is already running"})

    try:
        # main.py를 새 프로세스로 실행
        process = subprocess.Popen(["python3", "main.py"], cwd=BASE_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        pid = process.pid
        custom_logger.info(f"Trading bot started with PID: {pid}")
        
        # 상태 파일 업데이트 (실행 후 약간의 지연을 두어 상태 확인)
        time.sleep(1)  # 봇이 상태를 기록할 시간을 줌
        if psutil.pid_exists(pid):
            update_bot_status({"status": "running", "pid": pid})
            return jsonify({"status": "success", "message": f"Trading bot started with PID: {pid}"})
        else:
            return jsonify({"status": "error", "message": "Bot failed to start"})
    except Exception as e:
        custom_logger.error(f"Error starting bot: {str(e)}")
        return jsonify({"status": "error", "message": str(e)})

@app.route('/stop', methods=['POST'])
def stop_bot():
    status = get_bot_status()
    if status["status"] == "stopped":
        custom_logger.info("Bot is already stopped.")
        return jsonify({"status": "success", "message": "Bot is already stopped"})

    pid = status["pid"]
    if not pid or not psutil.pid_exists(pid):
        custom_logger.warning("No valid PID found, resetting status.")
        update_bot_status({"status": "stopped", "pid": None})
        return jsonify({"status": "success", "message": "No running bot found, status reset"})

    try:
        process = psutil.Process(pid)
        process.terminate()  # SIGTERM 신호로 종료 요청
        process.wait(timeout=5)  # 5초 대기
        custom_logger.info(f"Trading bot with PID {pid} stopped gracefully.")
        update_bot_status({"status": "stopped", "pid": None})
        return jsonify({"status": "success", "message": "Trading bot stopped"})
    except psutil.TimeoutExpired:
        process.kill()  # 강제 종료
        custom_logger.info(f"Trading bot with PID {pid} forcefully stopped.")
        update_bot_status({"status": "stopped", "pid": None})
        return jsonify({"status": "success", "message": "Trading bot forcefully stopped"})
    except Exception as e:
        custom_logger.error(f"Error stopping bot: {str(e)}")
        return jsonify({"status": "error", "message": str(e)})


# @app.route('/start', methods=['POST'])
def start_bot1():
    status = get_bot_status()
    if status["status"] == "running":
        return jsonify({"status": "error", "message": "Bot is already running"})
    try:
        process = subprocess.Popen(["python", "main.py"], cwd=os.getcwd())
        custom_logger.info(f"Trading bot started with PID: {process.pid}")
        return jsonify({"status": "success", "message": "Trading bot started"})
    except Exception as e:
        custom_logger.error(f"Error starting bot: {str(e)}")
        return jsonify({"status": "error", "message": str(e)})

# @app.route('/stop', methods=['POST'])
def stop_bot1():
    status = get_bot_status()
    if status["status"] == "stopped":
        return jsonify({"status": "success", "message": "Bot is already stopped"})
    try:
        pid = status["pid"]
        if pid:
            process = psutil.Process(pid)
            process.terminate()
            process.wait(timeout=5)
            logger.info("Trading bot stopped")
            return jsonify({"status": "success", "message": "Trading bot stopped"})
    except psutil.TimeoutExpired:
        process.kill()
        logger.info("Trading bot forcefully stopped")
        return jsonify({"status": "success", "message": "Trading bot forcefully stopped"})
    except Exception as e:
        logger.error(f"Error stopping bot: {str(e)}")
        return jsonify({"status": "error", "message": str(e)})

@app.route('/restart', methods=['POST'])
def restart_bot():
    try:
        # 먼저 현재 봇 종료
        status = get_bot_status()
        if status["status"] == "running":
            pid = status["pid"]
            if pid and psutil.pid_exists(pid):
                process = psutil.Process(pid)
                process.terminate()
                process.wait(timeout=5)
                custom_logger.info(f"Existing bot with PID {pid} stopped for restart")
            else:
                custom_logger.warning("No valid running bot found for restart, proceeding to start")

        # 새 봇 실행
        process = subprocess.Popen(["python", "main.py"], cwd=BASE_DIR, 
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        new_pid = process.pid
        custom_logger.info(f"Restarting bot with new PID: {new_pid}")
        time.sleep(1)

        if psutil.pid_exists(new_pid):
            update_bot_status({"status": "running", "pid": new_pid})
            custom_logger.info(f"Bot restarted successfully with PID: {new_pid}")
            return jsonify({"status": "success", "message": f"Bot restarted with PID: {new_pid}"})
        else:
            custom_logger.error(f"Bot process {new_pid} failed to restart")
            return jsonify({"status": "error", "message": "Bot failed to restart"})
    except psutil.TimeoutExpired:
        process.kill()
        custom_logger.error(f"Bot process {pid} timed out during restart")
        return jsonify({"status": "error", "message": "Bot restart timed out"})
    except Exception as e:
        custom_logger.error(f"Error restarting bot: {str(e)}")
        return jsonify({"status": "error", "message": str(e)})

@app.route('/config', methods=['GET', 'POST'])
def update_config():
    if request.method == 'POST':
        try:
            config.COIN_LIST = request.form.getlist('coin_list')[0].split(',')
            config.TRADE_RATE = float(request.form['trade_rate'])
            config.TARGET_LEVERAGE = int(request.form['target_leverage'])
            logger.info("Configuration updated.")
            return jsonify({"status": "success", "message": "Configuration updated."})
        except Exception as e:
            logger.error(f"Error updating config: {str(e)}")
            return jsonify({"status": "error", "message": str(e)})
    else:
        return render_template('config.html', config=config)

@app.route('/get_config', methods=['GET'])
def get_config():
    try:
        current_config = {
            "coin_list": config.COIN_LIST,
            "trade_rate": config.TRADE_RATE,
            "target_leverage": config.TARGET_LEVERAGE
        }
        return jsonify({"status": "success", "config": current_config})
    except Exception as e:
        logger.error(f"Error getting config: {str(e)}")
        return jsonify({"status": "error", "message": str(e)})

@app.route('/data', methods=['GET'])  # 엔드포인트 추가
def get_data():
    try:
        session = Session()
        balance_data = session.query(BalanceData).all()
        position_data = session.query(PositionData).all()

        balance_data = {
            "wallet": balance_data[0].wallet,
            "total": balance_data[0].total,
            "free": balance_data[0].free,
            "used": balance_data[0].used,
            "pnl": balance_data[0].pnl
        } if balance_data else {}
        
        position_data_dict = {
            data.symbol: {
                "symbol": data.symbol,
                "avg_price": data.avg_price,
                "position_amount": data.position_amount,
                "leverage": data.leverage,
                "unrealized_profit": data.unrealized_profit,
                "breakeven_price": data.breakeven_price,
                "market_status": data.market_status
            } for data in position_data
        }
        return jsonify({"status": "success", "balance_data": balance_data, "position_data": position_data_dict})
    except Exception as e:
        logger.error(f"Error getting data: {str(e)}")
        return jsonify({"status": "error", "message": str(e)})
    finally:
        session.close()

@app.route('/coin_data/<symbol>', methods=['GET'])
@cross_origin()
def get_coin_data(symbol):
    """
    CoinData DB에서 특정 symbol의 캔들 데이터를 가져옵니다.
    
    :param symbol: 코인 심볼 (예: 'BTCUSDT')
    :return: JSON 형식의 캔들 데이터
    """
    # interval 파라미터를 쿼리에서 받음 (기본값: '1m')
    interval = request.args.get('interval', '1m')
    
    session = Session()
    try:
# 최신 데이터 200개를 가져오기 위해 내림차순 정렬 후 상위 200개
        candles = session.query(CoinData).filter_by(
            symbol=symbol,
            interval=interval
        ).order_by(CoinData.open_time.desc()).limit(200).all()

        if not candles:
            logger.warning(f"No data found for {symbol} with interval {interval}")
            return jsonify({"status": "error", "message": f"No data for {symbol} with interval {interval}"})

        # Lightweight Charts는 시간순(오름차순) 데이터를 요구하므로 다시 정렬
        candles = sorted(candles, key=lambda x: x.open_time)
        
        # Lightweight Charts에 맞는 형식으로 변환
        candle_data = [
            {
                "time": int(candle.open_time.timestamp()),  # 초 단위로 변환
                "open": float(candle.open),
                "high": float(candle.high),
                "low": float(candle.low),
                "close": float(candle.close),
                "volume": float(candle.volume)
            } for candle in candles
        ]
        
        # 디버깅용 출력 (선택적)
        # logger.info(f"Candle data fetched: {len(candle_data)} entries")
        return jsonify({"status": "success", "data": candle_data})
    
    except Exception as e:
        logger.error(f"Error getting coin data from DB: {str(e)}")
        return jsonify({"status": "error", "message": str(e)})
    finally:
        session.close()


@app.route('/logs', methods=['GET'])
def get_logs():
    try:
        all_logs = []
        for category, logs in custom_logger.memory_logs.items():
            all_logs.extend(list(logs))
        all_logs.sort(key=lambda x: x['timestamp'], reverse=True)
        return jsonify({'status': 'success', 'logs': all_logs[:100]})
    except Exception as e:
        logger.error(f"Error processing logs: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == "__main__":
    custom_logger.system("Web interface started")
    app.run(host='127.0.0.1', port=5000, debug=True, use_reloader=True)