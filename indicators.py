import pandas as pd
import pandas_ta as ta
from typing import Dict, List, Optional


class Indicators:
    def __init__(self):
        # 지표 기간 설정 (조정 가능)
        self.ema_fast_length = 20  # 단기 EMA
        self.ema_slow_length = 50  # 장기 EMA
        self.sma_short_length = 7
        self.sma_mid_length = 15
        self.sma_long_length = 50
        self.rsi_length = 10
        self.stoch_k_length = 5
        self.stoch_d_length = 3
        self.stoch_smooth = 3
        self.momentum_length = 5
        self.roc_length = 5
        self.cci_length = 10
        self.willr_length = 10
        self.adx_length = 10
        self.atr_length = 10
        self.macd_fast = 5
        self.macd_slow = 10
        self.macd_signal = 3
        self.bbands_length = 20
        self.bbands_std = 2.0
        self.fib_length = 20

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        종합적인 기술적 지표를 계산하는 함수
        :param df: OHLCV (Open, High, Low, Close, Volume) 데이터프레임
        :return: 계산된 지표가 추가된 데이터프레임
        """
        try:
            # 이동평균선 (EMA) - 가격의 단기 및 중기 추세를 부드럽게 나타냄
            df['EMA_fast'] = round(ta.ema(df['Close'], length=self.ema_fast_length), 4)  # 단기 EMA (20): 빠른 가격 변동 추적
            df['EMA_slow'] = round(ta.ema(df['Close'], length=self.ema_slow_length), 4)  # 장기 EMA (50): 중기 추세 확인

            # 이동평균선 (SMA) - 단순 평균으로 가격 추세를 안정적으로 보여줌
            df['SMA_short'] = round(df['Close'].rolling(window=self.sma_short_length).mean(), 4)  # 단기 SMA (7): 초단기 추세 파악
            df['SMA_mid'] = round(df['Close'].rolling(window=self.sma_mid_length).mean(), 4)  # 중기 SMA (15): 단기 추세 확인
            df['SMA_long'] = round(df['Close'].rolling(window=self.sma_long_length).mean(), 4)  # 장기 SMA (20): 중기 추세 안정성 검증

            # 모멘텀 지표 - 가격의 상승/하락 속도와 과매수/과매도 상태 탐지
            df['RSI'] = round(ta.rsi(df['Close'], length=self.rsi_length), 4)  # RSI (10): 가격 모멘텀과 과매도/과매수 판단
            stoch = round(ta.stoch(df['High'], df['Low'], df['Close'], k=self.stoch_k_length, d=self.stoch_d_length, smooth_k=self.stoch_smooth), 4)  # Stochastic (5,3,3): 빠른 과매수/과매도 신호
            stoch.columns = ['STOCH_k', 'STOCH_d']
            df = pd.concat([df, stoch], axis=1)
            df['Momentum'] = round(ta.mom(df['Close'], length=self.momentum_length), 4)  # Momentum (5): 단기 가격 변화 속도
            df['ROC'] = round(ta.roc(df['Close'], length=self.roc_length), 4)  # ROC (5): 단기 가격 변화율로 모멘텀 확인
            df['CCI'] = round(ta.cci(df['High'], df['Low'], df['Close'], length=self.cci_length), 4)  # CCI (10): 가격 변동성과 과매도/과매수 탐지
            df['Williams_R'] = round(ta.willr(df['High'], df['Low'], df['Close'], length=self.willr_length), 4)  # Williams %R (10): 과매수/과매도 상태 파악

            # 추세 지표 - 추세 강도와 방향을 측정
            adx = round(ta.adx(df['High'], df['Low'], df['Close'], length=self.adx_length), 4)  # ADX (10): 단기 추세 강도와 방향성
            adx.columns = ['ADX', 'DMP', 'DMN']
            df = pd.concat([df, adx], axis=1)
            macd = round(ta.macd(df['Close'], fast=self.macd_fast, slow=self.macd_slow, signal=self.macd_signal), 4)  # MACD (5,10,3): 단기 추세 전환과 모멘텀
            macd.columns = ['MACD', 'MACD_histogram', 'MACD_signal']
            df = pd.concat([df, macd], axis=1)

            # 변동성 지표 - 가격 변동 범위와 리스크 측정
            df['ATR'] = round(ta.atr(df['High'], df['Low'], df['Close'], length=self.atr_length), 4)  # ATR (10): 단기 가격 변동성으로 리스크 관리

            # 볼린저 밴드 - 가격 범위와 변동성 기반 반전 신호
            bb = round(ta.bbands(df['Close'], length=self.bbands_length, std=self.bbands_std), 4)  # Bollinger Bands (20, std=2.0): 단기 가격 범위와 반전 포착
            bb.columns = ['BB_lower', 'BB_middle', 'BB_upper', 'BBB', 'BBP']
            df = pd.concat([df, bb], axis=1)

            # 피보나치 되돌림 레벨 - 단기 지지/저항 레벨 계산
            recent_high = round(df['High'].rolling(self.fib_length).max(), 4)  # 최근 20분 고가: 단기 지지/저항 기준
            recent_low = round(df['Low'].rolling(self.fib_length).min(), 4)  # 최근 20분 저가: 단기 지지/저항 기준
            df['fib_0.236'] = recent_high - (recent_high - recent_low) * 0.236  # 23.6% 되돌림: 약한 지지/저항
            df['fib_0.5'] = recent_high - (recent_high - recent_low) * 0.5  # 50% 되돌림: 중간 지지/저항
            df['fib_0.786'] = recent_high - (recent_high - recent_low) * 0.786  # 78.6% 되돌림: 강한 지지/저항
            df['fib_0.618'] = recent_high - (recent_high - recent_low) * 0.618  # 61.8% 되돌림: 주요 지지/저항

            return df.dropna()
        except Exception as e:
            print(f"지표 계산 중 오류: {e}")
            return "Error_State"

    def calculate_orderbook_indicators(self, orderbook: Dict) -> Dict:
        """
        orderbook_data를 활용한 지표 계산
        :param orderbook_data: orderbook 데이터 (bids, asks 포함)
        :return: 계산된 지표 (spread, order_imbalance, price_depth 등)
        """
        try:
            symbol = orderbook.get('s')
            bids = orderbook.get('b', [])
            asks = orderbook.get('a', [])

            # 호가 간격(Spread) - 매수/매도 최우선 호가 차이, 유동성 지표
            best_bid = float(bids[0][0]) if bids else 0
            best_ask = float(asks[0][0]) if asks else 0
            spread = round(best_ask - best_bid, 6)
            low_bid = float(bids[-1][0]) if bids else 0
            high_ask = float(asks[-1][0]) if asks else 0

            # 누적 주문량 차이(Order Imbalance) - 매수/매도 세력 불균형, 시장 심리 반영
            total_bid_volume = sum(float(bid[1]) for bid in bids)
            total_ask_volume = sum(float(ask[1]) for ask in asks)
            order_imbalance = round((total_bid_volume - total_ask_volume) / (total_bid_volume + total_ask_volume) if (total_bid_volume + total_ask_volume) > 0 else 0, 4)

            # 시장참여비율 (MPR) - 매수 압력 비율, 시장 방향성 판단
            mpr = round(total_bid_volume / (total_bid_volume + total_ask_volume), 4) if (total_bid_volume + total_ask_volume) > 0 else 0.5

            # 가격 깊이(Price Depth) - ±1% 범위 내 매수/매도 주문량, 유동성 측정
            current_price = (best_bid + best_ask) / 2
            price_range = current_price * 0.01
            bid_depth = round(sum(float(bid[1]) for bid in bids if current_price - price_range <= float(bid[0]) <= current_price), 4)
            ask_depth = round(sum(float(ask[1]) for ask in asks if current_price <= float(ask[0]) <= current_price + price_range), 4)

            return {
                'symbol': symbol,
                'high_ask': high_ask,
                'low_bid': low_bid,
                'spread': spread,
                'order_imbalance': order_imbalance,
                'bid_depth': bid_depth,
                'ask_depth': ask_depth,
                'mpr': mpr
            }
        except Exception as e:
            print(f"orderbook indicator 계산 중 오류: {e}")
            return "Error_State"

    def determine_market_status(self, df: pd.DataFrame) -> str:
        """ADX 기반 추세 강도 판단 (개선 버전)
        - 시장 상태를 추세 강도와 방향성으로 분류
        """
        try:
            # 1. 신호선 0 체크 - MACD 방향성과 강도 계산
            signal_line = df['MACD_signal'].iloc[-1]
            if signal_line == 0:
                macd_signal_rate_hour = 0
            else:
                macd_diff = abs(df['MACD'].iloc[-1] - signal_line)
                macd_signal_rate_hour = round((macd_diff / signal_line) * 100, 2)

            # 2. 이동평균선 조건 - 단기/중기 추세 방향성 판단
            is_rising_ma = (
                df['SMA_short'].iloc[-1] > df['SMA_mid'].iloc[-1] > df['SMA_long'].iloc[-1] and
                df['SMA_short'].iloc[-1] > df['SMA_short'].iloc[-2] and
                df['SMA_mid'].iloc[-1] > df['SMA_mid'].iloc[-2]
            )
            is_falling_ma = (
                df['SMA_short'].iloc[-1] < df['SMA_mid'].iloc[-1] < df['SMA_long'].iloc[-1] and
                df['SMA_short'].iloc[-1] < df['SMA_short'].iloc[-2] and
                df['SMA_mid'].iloc[-1] < df['SMA_mid'].iloc[-2]
            )

            # 3. MACD 조건 - 단기 추세 전환과 강도 확인
            macd_vals = df['MACD'].tail(3).values
            is_rising_macd = (
                df['MACD'].iloc[-1] > df['MACD_signal'].iloc[-1] and
                macd_vals[-1] > macd_vals[-2] > macd_vals[-3] and
                macd_signal_rate_hour > 10
            )
            is_falling_macd = (
                df['MACD'].iloc[-1] < df['MACD_signal'].iloc[-1] and
                macd_vals[-1] < macd_vals[-2] < macd_vals[-3] and
                macd_signal_rate_hour > 10
            )

            # 4. ADX 기반 추세 판단 - 추세 강도에 따라 상태 분류
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