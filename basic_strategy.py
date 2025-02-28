import pandas as pd
import pandas_ta as ta
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from config import COIN_LIST, TRADE_RATE
import logging
import time
from data_handler import DataHandler
from logger import logger

class BasicStrategy:
    def __init__(self, data_handler: DataHandler):
        self.trade_history = []  # 거래 내역 저장
        self.data_handler = data_handler
        self.active_strategies = ['_bollinger_rsi_strategy', '_macd_rsi_strategy']  # 초기값
        self.strategy_map = {
            'Strong_Trend_Up': ['_trend_momentum_strategy', '_volume_breakout_strategy'],
            'Rising': ['_trend_momentum_strategy', '_macd_rsi_strategy'],
            'Sideways_Or_Weak_Trend': ['_bollinger_rsi_strategy', '_macd_rsi_strategy'],
            'Falling': ['_atr_trend_follow_strategy', '_macd_rsi_strategy'],
            'Strong_Trend_Down': ['_atr_trend_follow_strategy', '_rsi_divergence_strategy']
        }

        logger.system(f"BasicStrategy Class 시작")
        self.nowtime = datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S')

    def set_market_status(self, market_status: str):
        """현재 시장 상태를 설정하고 상태 지속성 체크"""
        self.market_status = market_status
        self.active_strategies = self.strategy_map.get(market_status, [])

    def generate_trading_signals(self, df: pd.DataFrame, position: Dict, orderbook: Dict) -> Dict:
        """
        다중 조건 기반 매매 신호 생성
        - 상태 전환 시 손익률 기반 청산 추가
        """
        signals = {
            'symbol': orderbook['symbol'],
            'action': 'HOLD',
            'price': None,
            'amount': 0,
            'strategy': '',
            'reason': ''
        }

        # orderbook['market_status'] 값을 사용하여 시장 상태 설정
        market_status = position.get('market_status_1m')  # 키가 없을 경우 None 반환
        if market_status: # market_status가 None이 아닐경우
            self.set_market_status(market_status)  # 시장 상태 설정
            # self.set_market_status('Sideways_Or_Weak_Trend')  # 시장 상태 설정
            
        # 전략별 신호 생성
        strategy_handlers = {
            '_trend_momentum_strategy': self._trend_momentum_strategy,
            '_volume_breakout_strategy': self._volume_breakout_strategy,
            '_atr_trend_follow_strategy': self._atr_trend_follow_strategy,
            '_bollinger_rsi_strategy': self._bollinger_rsi_strategy,
            '_macd_rsi_strategy': self._macd_rsi_strategy,
            '_rsi_divergence_strategy': self._rsi_divergence_strategy
        }

        for strategy in self.active_strategies:
            handler = strategy_handlers.get(strategy)
            # handler = strategy_handlers[strategy]

            if handler:
                strategy_signal = handler(df, position,orderbook)
                # self.signals[symbol]['strategy'] = strategy
                if strategy_signal['action'] != 'HOLD':
                    strategy_signal['strategy'] = strategy
                    signals.update(strategy_signal)
                    time.sleep(0.5)
                    break  # 우선순위 전략 신호 사용

        return signals

    def _volume_breakout_strategy(self, df: pd.DataFrame, position: Dict, orderbook: Dict) -> Dict:
        """Strong_Trend_Up 변화 대응: 급등/급락 모멘텀 포착 (롱/숏)
        - 강한 상승장 초기에 롱 진입, 말기에는 숏 진입으로 수익 극대화
        """
        latest = df.iloc[-1]
        price_high = orderbook['high_ask']
        price_low = orderbook['low_bid']
        current_price = latest['Close']
        position_amount = position['position_amount']
        symbol = orderbook['symbol']
        signals = {
            'symbol': symbol,
            'action': 'HOLD',
            'price': None,
            'amount': 0,
            'reason': ''
        }

        # 설정값
        adx_threshold = 25
        atr_ma = df['ATR'].rolling(14).mean().iloc[-1]
        vol_ma = df['Volume'].rolling(20).mean().iloc[-1]

        # 롱 진입 조건: 강한 상승장 초기
        enter_long_cond = all([
            latest['Volume'] > vol_ma * 1.5,
            latest['MACD_histogram'] > df['MACD_histogram'].iloc[-2] * 1.2,
            latest['Close'] > latest['fib_0.786'],
            orderbook['mpr'] > 0.6,
            orderbook['order_imbalance'] > 0.2,
            latest['ADX'] < adx_threshold,
            latest['ATR'] < atr_ma * 2
            # self.status_duration >= 3,  # 상태 지속성 확인
        ])

        # 숏 진입 조건: 강한 상승장 말기
        enter_short_cond = all([
            # latest['Volume'] > vol_ma * 1.5,
            latest['MACD_histogram'] < df['MACD_histogram'].iloc[-2] * 0.8,
            latest['RSI'] > 70,
            current_price < latest['EMA_fast'],
            orderbook['mpr'] < 0.45,
            orderbook['order_imbalance'] < -0.2,
            latest['ADX'] > adx_threshold,
            latest['ATR'] < atr_ma * 2
        ])

        # 롱 청산 조건: 추세 약화 또는 상태 전환
        exit_long_cond = any([
            current_price < latest['EMA_slow'],
            orderbook['mpr'] < 0.4,
            latest['ATR'] > atr_ma * 2
            # self.market_status in ['Rising', 'Sideways_Or_Weak_Trend']  # 상태 전환 시 청산
        ])

        # 숏 청산 조건: 반등 신호
        exit_short_cond = any([
            current_price > latest['EMA_fast'],
            orderbook['mpr'] > 0.55,
            latest['ATR'] > atr_ma * 2
        ])

        # 포지션 없음: 신규 진입
        if enter_long_cond:
            if self._check_open_condition(position):
                size = self._calculate_order_size(current_price, position)
                signals.update({
                    'action': 'ENTER_LONG',
                    'price': price_high,
                    'amount': size,
                    'reason': f"급등신호롱진입(VOL:{latest['Volume']/vol_ma:.1f}x/MPR:{orderbook['mpr']:.2f})"
                })
                return signals
        elif enter_short_cond:
            if self._check_open_condition(position):
                size = self._calculate_order_size(current_price, position)
                signals.update({
                    'action': 'ENTER_SHORT',
                    'price': price_low,
                    'amount': size,
                    'reason': f"급등종료숏진입(VOL:{latest['Volume']/vol_ma:.1f}x/MPR:{orderbook['mpr']:.2f})"
                })
                return signals

        # 포지션 보유 중: 빠른 청산
        elif position_amount > 0 and exit_long_cond:
            if self._check_close_condition(position):
                size = abs(self._calculate_order_size(current_price, position))
                signals.update({
                    'action': 'EXIT_LONG',
                    'price': price_low,
                    'amount': size,
                    'reason': f"급등종료롱청산(VOL:{latest['Volume']/vol_ma:.1f}x/MPR:{orderbook['mpr']:.2f})"
                })
                return signals
        elif position_amount < 0 and exit_short_cond:
            if self._check_close_condition(position):
                size = abs(self._calculate_order_size(current_price, position))
                signals.update({
                    'action': 'EXIT_SHORT',
                    'price': price_high,
                    'amount': size,
                    'reason': f"급등신호숏청산(VOL:{latest['Volume']/vol_ma:.1f}x/MPR:{orderbook['mpr']:.2f})"
                })
                return signals

        return signals

    def _trend_momentum_strategy(self, df: pd.DataFrame, position: Dict, orderbook: Dict) -> Dict:
        """공유 전략: Strong_Trend_Up 및 Rising 주요 흐름 - 지속적 상승/하락 추세 추종 (롱/숏)
        - 단기 매매에서 상승 및 하락 추세를 모두 추적하며 양방향 진입과 빠른 청산
        """
        latest = df.iloc[-1]
        price_high = orderbook['high_ask']  # 롱 진입/숏 청산 시 매수 호가
        price_low = orderbook['low_bid']    # 숏 진입/롱 청산 시 매도 호가
        current_price = latest['Close']
        position_amount = position['position_amount']
        symbol = orderbook['symbol']
        signals = {
            'symbol': symbol,
            'action': 'HOLD',
            'price': None,
            'amount': 0,
            'reason': ''
        }

        # 설정값 (Thresholds)
        adx_threshold = 25 if self.market_status == 'Strong_Trend_Up' else 22  # 상태별 ADX 기준 (조정 가능: 20~27)
        atr_ma = df['ATR'].rolling(14).mean().iloc[-1]  # 평균 ATR 계산 (변동성 기준)
        volume_trend = df['Volume'].iloc[-3:].mean() > df['Volume'].rolling(20).mean().iloc[-2]  # 최근 3봉 거래량 상승

        # 진입 조건: 신중한 추세 방향 확인
        enter_long_cond = all([
            latest['EMA_slow'] > latest['EMA_fast'],  # EMA_slow > EMA_fast: 상승 추세 확인
            latest['ADX'] > adx_threshold,  # ADX 기준: 상승 추세 강도 (ADX_14 → ADX)
            volume_trend,  # 거래량 증가로 모멘텀 검증
            orderbook['mpr'] > 0.55 and orderbook['bid_depth'] > orderbook['ask_depth'] * 1.2,  # 매수 압력 강함
            latest['ATR'] < atr_ma * 1.5  # 변동성 안정 (조정 가능: 1.2~2)
        ])

        enter_short_cond = all([
            latest['EMA_slow'] < latest['EMA_fast'],  # EMA_slow < EMA_fast: 하락 추세 확인
            latest['ADX'] > adx_threshold,  # ADX 기준: 하락 추세 강도
            # volume_trend,  # 거래량 증가로 모멘텀 검증
            latest['RSI'] > 70,
            orderbook['mpr'] < 0.45 and orderbook['ask_depth'] > orderbook['bid_depth'] * 1.2,  # 매도 압력 강함
            latest['ATR'] < atr_ma * 1.5  # 변동성 안정
        ])

        # 청산 조건: 빠른 추세 약화 또는 반전 대응
        exit_long_cond = all([
            current_price < latest['EMA_fast'],  # EMA_slow 이탈: 상승 추세 약화
            # latest['ADX'] < adx_threshold - 5,  # ADX 감소: 추세 소멸
            orderbook['mpr'] < 0.45,  # 매수 압력 급감 (조정 가능: 0.35~0.45)
            latest['ATR'] > atr_ma * 2  # 변동성 급등: 리스크 관리
        ])

        exit_short_cond = all([
            current_price > latest['EMA_fast'],  # EMA_slow 돌파: 하락 추세 약화
            # latest['ADX'] < adx_threshold - 5,  # ADX 감소: 추세 소멸
            orderbook['mpr'] > 0.55,  # 매도 압력 감소 (조정 가능: 0.5~0.6)
            latest['ATR'] > atr_ma * 2  # 변동성 급등: 리스크 관리
        ])

        # 포지션 없음: 신규 진입
        if enter_long_cond:
            if self._check_open_condition(position):
                size = self._calculate_order_size(current_price, position)
                signals.update({
                    'action': 'ENTER_LONG',
                    'price': price_high,
                    'amount': size,
                    'reason': f"상승추세(ADX:{latest['ADX']:.1f}/MPR:{orderbook['mpr']:.2f})"
                })
                return signals
        elif enter_short_cond:
            if self._check_open_condition(position):
                size = self._calculate_order_size(current_price, position)
                signals.update({
                    'action': 'ENTER_SHORT',
                    'price': price_low,
                    'amount': size,
                    'reason': f"하락추세(ADX:{latest['ADX']:.1f}/MPR:{orderbook['mpr']:.2f})"
                })
                return signals

        # 포지션 보유 중: 빠른 청산
        elif position_amount > 0 and exit_long_cond:
            if self._check_close_condition(position):
                size = abs(self._calculate_order_size(current_price, position))
                signals.update({
                    'action': 'EXIT_LONG',
                    'price': price_low,
                    'amount': size,
                    'reason': f"상승추세약화(ADX:{latest['ADX']:.1f}/MPR:{orderbook['mpr']:.2f})"
                })
                return signals
        elif position_amount < 0 and exit_short_cond:
            if self._check_close_condition(position):
                size = abs(self._calculate_order_size(current_price, position))
                signals.update({
                    'action': 'EXIT_SHORT',
                    'price': price_high,
                    'amount': size,
                    'reason': f"하락추세약화(ADX:{latest['ADX']:.1f}/MPR:{orderbook['mpr']:.2f})"
                })
                return signals

        return signals
    
    def _macd_rsi_strategy(self, df: pd.DataFrame, position: Dict, orderbook: Dict) -> Dict:
        """
        MACD + RSI 전략 - Rising, Falling, Sideways_Or_Weak_Trend에서 사용
        - 포지션 진입은 신중히, 청산은 신속히 수행
        - 단기 추세 전환 및 조정 포착에 초점
        """
        latest = df.iloc[-1]
        price_high = orderbook['high_ask']  # 롱 진입/숏 청산 시 매수 호가
        price_low = orderbook['low_bid']    # 숏 진입/롱 청산 시 매도 호가
        current_price = latest['Close']
        avg_price = position['avg_price']
        position_amount = position['position_amount']
        leverage = position['leverage']
        symbol = orderbook['symbol']
        
        signals = {
            'symbol': symbol,
            'action': 'HOLD',
            'price': None,
            'amount': 0,
            'reason': ''
        }
        
        # 오더북 지표
        mpr = orderbook['mpr']  # 시장 압력 비율 (Market Pressure Ratio)

        # RSI 계산
        rsi = df['RSI']  # rsi → RSI
        rsi_now = round(rsi.iloc[-1], 3)  # 현재 RSI 값
        rsi_min = round(rsi.iloc[-7:-2].min(), 3)  # 최근 7~2봉 RSI 최소값

        # MACD 계산
        macd = df['MACD']  # MACD_12_26_9 → MACD
        histogram = df['MACD_histogram']  # MACDh_12_26_9 → MACD_histogram
        macd_signal = df['MACD_signal']  # MACDs_12_26_9 → MACD_signal
        macd_signal_rate = round(
            abs((macd.iloc[-1] - macd_signal.iloc[-1]) / macd_signal.iloc[-1] * 100)
            if macd_signal.iloc[-1] != 0 else 0, 2
        )  # MACD와 신호선 간 비율 차이

        # 캔들 변화율 (추가 검증용)
        close_data = df['Close']
        open_data = df['Open']
        upraise = round(((close_data.iloc[-1] - open_data.iloc[-1]) / open_data.iloc[-1] * 100)
                        if open_data.iloc[-1] != 0 else 0, 2)  # 현재 캔들 상승률
        pre_upraise = round(((close_data.iloc[-2] - open_data.iloc[-2]) / open_data.iloc[-2] * 100)
                            if open_data.iloc[-2] != 0 else 0, 2)  # 이전 캔들 상승률

        # 현재 포지션 수익률 (레버리지 반영)
        mygain = ((current_price - avg_price) / avg_price * 100 * leverage) if avg_price != 0 and position_amount != 0 else 0

        # 캔들 변동 조건: 과도한 변동 방지
        raise_condition = abs(pre_upraise) < 0.4 and abs(upraise) <= 0.3

        # MACD 상승 추세 전환 (Upward Change)
        macd_up_change = (
            macd.iloc[-1] > macd.iloc[-2] and
            macd.iloc[-2] >= macd.iloc[-3] and
            macd.iloc[-3] <= macd.iloc[-4] and
            macd.iloc[-4] < macd.iloc[-5] and
            histogram.iloc[-1] < 0 and
            macd_signal_rate > 10
        )
        
        # MACD 하락 추세 전환 (Downward Change)
        macd_down_change = (
            macd.iloc[-1] < macd.iloc[-2] and
            macd.iloc[-2] <= macd.iloc[-3] and
            macd.iloc[-3] >= macd.iloc[-4] and
            macd.iloc[-4] > macd.iloc[-5] and
            histogram.iloc[-1] > 0 and
            macd_signal_rate > 10
        )
        
        # MACD 골든크로스 조건
        macd_golden_cross = (
            histogram.iloc[-1] > histogram.iloc[-2] > histogram.iloc[-3] and
            histogram.iloc[-4:-1].mean() < 0 and
            (histogram.iloc[-1] > 0 or histogram.iloc[-2] > 0) and
            macd_signal_rate > 10
        )
        
        # MACD 데드크로스 조건
        macd_dead_cross = (
            histogram.iloc[-1] < histogram.iloc[-2] < histogram.iloc[-3] and
            histogram.iloc[-4:-1].mean() > 0 and
            (histogram.iloc[-1] < 0 or histogram.iloc[-2] < 0) and
            macd_signal_rate > 10
        )

        # 추가 - 배드 포지션 청산 조건 (장기 보유 시 손절매)
        histogram_down_condition = (
            position_amount > 0 and mygain < -10 and
            histogram.iloc[-1] <= 0 and
            histogram.iloc[-1] <= histogram.iloc[-2] < histogram.iloc[-3]
        )  # 롱 포지션 손실 과다 시 청산
        histogram_up_condition = (
            position_amount < 0 and mygain < -10 and
            histogram.iloc[-1] >= 0 and
            histogram.iloc[-1] >= histogram.iloc[-2] > histogram.iloc[-3]
        )  # 숏 포지션 손실 과다 시 청산

        # 쓰레드홀드 변수화
        rsi_lower = 45  # 조정 가능: 30~40
        rsi_upper = 55  # 조정 가능: 60~70
        rsi_lower_cond = latest['RSI'] < rsi_lower and rsi_min < 35 # RSI 과매도 (rsi → RSI)
        rsi_upper_cond = latest['RSI'] > rsi_upper and rsi_min > 65 # RSI 과매수 (rsi → RSI)
        

        # 포지션 진입 조건 (신중하게)
        enter_long_condition = (
            (macd_up_change or macd_golden_cross) and
            raise_condition and
            rsi_lower_cond and
            mpr > 0.55
        )
        enter_short_condition = (
            (macd_down_change or macd_dead_cross) and
            raise_condition and
            rsi_upper_cond and
            mpr < 0.45
        )

        # 포지션 청산 조건 (신속하게)
        exit_long_condition = (
            (macd_down_change or macd_dead_cross) and
            mpr < 0.45
        )
        exit_short_condition = (
            (macd_up_change or macd_golden_cross) and
            mpr > 0.55
        )

        # 신규 진입 또는 추가 진입
        if self._check_open_condition(position):
            if enter_long_condition:
                size = self._calculate_order_size(current_price, position)
                signals.update({
                    'action': 'ENTER_LONG',
                    'price': price_high,
                    'amount': size,
                    'reason': f"MACD Up/Golden Cross, RSI {rsi_now:.1f}, rsi_min {rsi_min}, MPR {mpr}"
                })
                return signals
            elif enter_short_condition:
                size = self._calculate_order_size(current_price, position)
                signals.update({
                    'action': 'ENTER_SHORT',
                    'price': price_low,
                    'amount': size,
                    'reason': f"MACD Down/Dead Cross, Price {current_price:.2f} > Avg {avg_price:.2f}, MPR {mpr}"
                })
                return signals

        # 포지션 보유 중 청산
        elif self._check_close_condition(position):
            if position_amount > 0 and exit_long_condition:
                size = abs(self._calculate_order_size(current_price, position))
                signals.update({
                    'action': 'EXIT_LONG',
                    'price': price_low,
                    'amount': size,
                    'reason': f"MACD Down/Dead Cross, MPR {mpr}"
                })
                return signals
            elif position_amount < 0 and exit_short_condition:
                size = abs(self._calculate_order_size(current_price, position))
                signals.update({
                    'action': 'EXIT_SHORT',
                    'price': price_high,
                    'amount': size,
                    'reason': f"MACD Up/Golden Cross, MPR {mpr}"
                })
                return signals
        # 배드 포지션 청산
        elif histogram_down_condition:
            size = abs(self._calculate_order_size(current_price, position))
            signals.update({
                'action': 'EXIT_LONG',
                'price': price_low,
                'amount': size,
                'reason': f"Histogram Down, mygain {mygain}"
            })
            return signals
        elif histogram_up_condition:
            size = abs(self._calculate_order_size(current_price, position))
            signals.update({
                'action': 'EXIT_SHORT',
                'price': price_high,
                'amount': size,
                'reason': f"Histogram Up, mygain {mygain}"
            })

        return signals

    def _bollinger_rsi_strategy(self, df: pd.DataFrame, position: Dict, orderbook: Dict) -> Dict:
        """볼린저 밴드 + RSI 스캘핑 전략 - Sideways_Or_Weak_Trend에서 사용
        - 횡보 범위 내 평균 회귀를 타겟팅하며 신중한 진입과 빠른 청산
        """
        latest = df.iloc[-1]
        price_high = orderbook['high_ask']  # 롱 진입/숏 청산 시 매수 호가
        price_low = orderbook['low_bid']    # 숏 진입/롱 청산 시 매도 호가
        current_price = latest['Close']
        avg_price = position['avg_price']
        position_amount = position['position_amount']
        symbol = orderbook['symbol']
        signals = {
            'symbol': symbol,
            'action': 'HOLD',
            'price': None,
            'amount': 0,
            'reason': ''
        }

        # 쓰레드홀드 변수화
        rsi_lower = 35  # 조정 가능: 30~40
        rsi_upper = 65  # 조정 가능: 60~70
        atr_ma = df['ATR'].rolling(14).mean().iloc[-1]  # atr → ATR

        # 진입 조건: 신중한 평균 회귀 신호
        bb_lower_condition = current_price < latest['BB_lower']  # 볼린저 하단 이탈 (유지)
        bb_upper_condition = current_price > latest['BB_upper']  # 볼린저 상단 돌파 (유지)
        rsi_lower_cond = latest['RSI'] < rsi_lower  # RSI 과매도 (rsi → RSI)
        rsi_upper_cond = latest['RSI'] > rsi_upper  # RSI 과매수 (rsi → RSI)
        volume_trend = df['Volume'].iloc[-3:].mean() > df['Volume'].rolling(20).mean().iloc[-2]  # 최근 3봉 평균 거래량 상승
        orderbook_long = orderbook['mpr'] > 0.55 and orderbook['order_imbalance'] > 0.2  # 매수 압력
        orderbook_short = orderbook['mpr'] < 0.45 and orderbook['order_imbalance'] < -0.2  # 매도 압력

        enter_long_cond = all([
            bb_lower_condition,  # 볼린저 하단 반전
            rsi_lower_cond,  # 과매도 상태
            volume_trend,  # 거래량 모멘텀
            orderbook_long,  # 오더북 매수 심리
            latest['ATR'] < atr_ma * 1.5  # 변동성 안정 
        ])

        enter_short_cond = all([
            bb_upper_condition,  # 볼린저 상단 반전
            rsi_upper_cond,  # 과매수 상태
            volume_trend,  # 거래량 모멘텀
            orderbook_short,  # 오더북 매도 심리
            latest['ATR'] < atr_ma * 1.5  # 변동성 안정 (atr → ATR)
        ])

        # 청산 조건: 빠른 범위 이탈 대응
        exit_long_cond = all([
            current_price > latest['BB_middle'],  # 볼린저 중간선 복귀 (유지)
            latest['RSI'] > 65,  # RSI 중립 이상 (rsi → RSI)
            orderbook['mpr'] < 0.5,  # 매수 압력 급감
            latest['ATR'] > atr_ma * 2  # 변동성 급등 (atr → ATR)
        ])

        exit_short_cond = all([
            current_price < latest['BB_middle'],  # 볼린저 중간선 복귀 (유지)
            latest['RSI'] < 35,  # RSI 중립 이하 (rsi → RSI)
            orderbook['mpr'] > 0.5,  # 매도 압력 감소
            latest['ATR'] > atr_ma * 2  # 변동성 급등 (atr → ATR)
        ])

        # 포지션 없음: 신규 진입
        if enter_long_cond:
            if self._check_open_condition(position):
                size = self._calculate_order_size(current_price, position)
                signals.update({
                    'action': 'ENTER_LONG',
                    'price': price_high,
                    'amount': size,
                    'reason': f"BB하단반전(RSI:{latest['RSI']:.1f}/MPR:{orderbook['mpr']:.2f})"
                })
                return signals
        elif enter_short_cond:
            if self._check_open_condition(position):
                size = self._calculate_order_size(current_price, position)
                signals.update({
                    'action': 'ENTER_SHORT',
                    'price': price_low,
                    'amount': size,
                    'reason': f"BB상단반전(RSI:{latest['RSI']:.1f}/MPR:{orderbook['mpr']:.2f})"
                })
                return signals

        # 포지션 보유 중: 빠른 청산
        elif position_amount > 0 and exit_long_cond:
            if self._check_close_condition(position):
                size = abs(self._calculate_order_size(current_price, position))
                signals.update({
                    'action': 'EXIT_LONG',
                    'price': price_low,
                    'amount': size,
                    'reason': f"중심선복귀(RSI:{latest['RSI']:.1f}/MPR:{orderbook['mpr']:.2f})"
                })
                return signals
        elif position_amount < 0 and exit_short_cond:
            if self._check_close_condition(position):
                size = abs(self._calculate_order_size(current_price, position))
                signals.update({
                    'action': 'EXIT_SHORT',
                    'price': price_high,
                    'amount': size,
                    'reason': f"중심선복귀(RSI:{latest['RSI']:.1f}/MPR:{orderbook['mpr']:.2f})"
                })
        return signals

    def _atr_trend_follow_strategy(self, df: pd.DataFrame, position: Dict, orderbook: Dict) -> Dict:
        """공유 전략: Falling 및 Strong_Trend_Down 주요 흐름 - 변동성 확장 추세 추종 (롱/숏)
        - 단기 매매에서 완만/강한 하락 및 반등 추세를 모두 추적하며 양방향 대응
        """
        latest = df.iloc[-1]
        price_high = orderbook['high_ask']  # 롱 진입/숏 청산 시 매수 호가
        price_low = orderbook['low_bid']    # 숏 진입/롱 청산 시 매도 호가
        current_price = latest['Close']
        position_amount = position['position_amount']
        symbol = orderbook['symbol']
        signals = {
            'symbol': symbol,
            'action': 'HOLD',
            'price': None,
            'amount': 0,
            'reason': ''
        }

        # 설정값 (Thresholds)
        adx_threshold = 32  # Falling과 Strong_Trend_Down 기준 (조정 가능: 30~35)
        atr_ma = df['ATR'].rolling(14).mean().iloc[-1]  # 평균 ATR 계산
        atr_threshold = 1.4  # 변동성 확장 기준 (조정 가능: 1.3~1.5)

        # 진입 조건: 신중한 추세 확인
        enter_short_cond = all([
            latest['ATR'] > atr_ma * atr_threshold,  # ATR 증가: 변동성 확장
            latest['ADX'] > adx_threshold,  # ADX 기준: 강한 하락 추세
            (latest['BB_upper'] - latest['BB_lower']) > df['BB_upper'].diff().rolling(5).mean().iloc[-1] * 2,  # 볼린저 밴드 확장
            df['Low'].iloc[-3:].is_monotonic_decreasing,  # 최근 3봉 저점 하락
            orderbook['ask_depth'] > orderbook['bid_depth'] * 1.8,  # 매도 압력 강함
            orderbook['mpr'] < 0.45,  # 시장 압력 약세
            self._check_open_condition(position)
        ])

        enter_long_cond = all([
            latest['ATR'] > atr_ma * atr_threshold,  # ATR 증가: 변동성 확장
            latest['ADX'] > adx_threshold,  # ADX 기준: 강한 추세 (하락 후 반등 가능성)
            (latest['BB_upper'] - latest['BB_lower']) > df['BB_upper'].diff().rolling(5).mean().iloc[-1] * 2,  # 볼린저 밴드 확장
            df['High'].iloc[-3:].is_monotonic_increasing,  # 최근 3봉 고점 상승: 반등 신호
            orderbook['bid_depth'] > orderbook['ask_depth'] * 1.8,  # 매수 압력 강함
            orderbook['mpr'] > 0.55,  # 시장 압력 강세
            self._check_open_condition(position)
        ])

        # 청산 조건: 빠른 추세 완화 대응
        exit_short_cond = all([
            latest['ATR'] < atr_ma * 0.8,  # ATR 감소: 변동성 축소
            latest['ADX'] < adx_threshold - 5,  # ADX 감소: 추세 약화
            current_price > latest['BB_middle'],  # 볼린저 중간선 돌파: 반등 신호
            orderbook['mpr'] > 0.55,  # 매수 압력 증가
            latest['ATR'] > atr_ma * 2.5  # 변동성 급등: 리스크 관리
        ])

        exit_long_cond = all([
            latest['ATR'] < atr_ma * 0.8,  # ATR 감소: 변동성 축소
            latest['ADX'] < adx_threshold - 5,  # ADX 감소: 추세 약화
            current_price < latest['BB_middle'],  # 볼린저 중간선 이탈: 반등 종료
            orderbook['mpr'] < 0.45,  # 매수 압력 감소
            latest['ATR'] > atr_ma * 2.5  # 변동성 급등: 리스크 관리
        ])
        # 긴급 청산: 손실 제한
        emergency_exit = all([
            latest['ATR'] > atr_ma * 2.5,  # 극단적 변동성 확대 (atr → ATR)
            abs(current_price - position['avg_price']) > current_price * 0.05  # 5% 이상 변동
        ])

        # 포지션 없음: 신규 진입
        if enter_short_cond:
            if self._check_open_condition(position):
                size = self._calculate_order_size(current_price, position)
                signals.update({
                    'action': 'ENTER_SHORT',
                    'price': price_low,
                    'amount': size,
                    'reason': f"하락추세(ATR:{latest['ATR']:.2f}/ADX:{latest['ADX']:.1f})"
                })
                return signals
        elif enter_long_cond:
            if self._check_open_condition(position):
                size = self._calculate_order_size(current_price, position)
                signals.update({
                    'action': 'ENTER_LONG',
                    'price': price_high,
                    'amount': size,
                    'reason': f"반등추세(ATR:{latest['ATR']:.2f}/ADX:{latest['ADX']:.1f})"
                })
                return signals

        # 포지션 보유 중: 빠른 청산
        elif position_amount < 0 and exit_short_cond:
            if self._check_close_condition(position):
                size = abs(self._calculate_order_size(current_price, position))
                signals.update({
                    'action': 'EXIT_SHORT',
                    'price': price_high,
                    'amount': size,
                    'reason': f"추세완화(ATR:{latest['ATR']:.2f}/MPR:{orderbook['mpr']:.2f})"
                })
                return signals
        elif position_amount > 0 and exit_long_cond:
            if self._check_close_condition(position):
                size = abs(self._calculate_order_size(current_price, position))
                signals.update({
                    'action': 'EXIT_LONG',
                    'price': price_low,
                    'amount': size,
                    'reason': f"반등종료(ATR:{latest['ATR']:.2f}/MPR:{orderbook['mpr']:.2f})"
                })
                return signals
            
        elif position_amount > 0 and emergency_exit and self._check_close_condition(position):
            size = self._calculate_order_size(current_price, position)
            signals.update({
                'action': 'EXIT_LONG',
                'price': orderbook['low_bid'],
                'amount': position_amount,
                'reason': f"긴급청산(ATR:{latest['ATR']:.2f}/변동:{abs(current_price - position['avg_price'])/current_price:.2%})"
            })

        return signals

    def _rsi_divergence_strategy(self, df: pd.DataFrame, position: Dict, orderbook: Dict) -> Dict:
        """Strong_Trend_Down 변화 대응: RSI 다이버전스 반등/하락 전략 (롱/숏)
        - 단기 매매에서 강한 하락 후 반등 및 추가 하락을 포착하며 양방향 대응
        """
        latest = df.iloc[-1]
        price_high = orderbook['high_ask']  # 롱 진입/숏 청산 시 매수 호가
        price_low = orderbook['low_bid']    # 숏 진입/롱 청산 시 매도 호가
        current_price = latest['Close']
        position_amount = position['position_amount']
        symbol = orderbook['symbol']
        signals = {
            'symbol': symbol,
            'action': 'HOLD',
            'price': None,
            'amount': 0,
            'reason': ''
        }

        # 설정값 (Thresholds)
        adx_threshold = 25  # Strong_Trend_Down 기준 (조정 가능: 20~30)
        rsi_lower = 30  # 과매도 기준 (조정 가능: 25~35)
        rsi_upper = 70  # 과매수 기준 (조정 가능: 65~75)
        atr_ma = df['ATR'].rolling(14).mean().iloc[-1]  # 평균 ATR 계산

        # RSI 다이버전스 계산
        bullish_divergence = latest['RSI'] > df['RSI'].iloc[-2] and current_price < df['Close'].iloc[-2]  # RSI 상승 + 가격 하락
        bearish_divergence = latest['RSI'] < df['RSI'].iloc[-2] and current_price > df['Close'].iloc[-2]  # RSI 하락 + 가격 상승

        # 진입 조건: 신중한 추세 반전 확인
        enter_long_cond = all([
            bullish_divergence,  # RSI 다이버전스: 반등 신호
            latest['RSI'] < rsi_lower,  # RSI 강한 과매도
            current_price < latest['BB_lower'],  # 볼린저 하단 근처
            orderbook['mpr'] > 0.5,  # 매수 압력 회복
            orderbook['bid_depth'] > orderbook['ask_depth'] * 1.5,  # 매수 깊이 우세
            df['Volume'].iloc[-3:].mean() > df['Volume'].rolling(20).mean().iloc[-2],  # 최근 3봉 거래량 상승
            latest['ADX'] < adx_threshold,  # ADX 약함: 추세 약화
            latest['ATR'] < atr_ma * 1.5,  # 변동성 안정
            self._check_open_condition(position)
        ])

        enter_short_cond = all([
            bearish_divergence,  # RSI 다이버전스: 하락 신호
            latest['RSI'] > rsi_upper,  # RSI 강한 과매수
            current_price > latest['BB_upper'],  # 볼린저 상단 근처
            orderbook['mpr'] < 0.45,  # 매도 압력 강함
            orderbook['ask_depth'] > orderbook['bid_depth'] * 1.5,  # 매도 깊이 우세
            df['Volume'].iloc[-3:].mean() > df['Volume'].rolling(20).mean().iloc[-2],  # 최근 3봉 거래량 상승
            latest['ADX'] < adx_threshold,  # ADX 약함: 추세 약화
            latest['ATR'] < atr_ma * 1.5,  # 변동성 안정
            self._check_open_condition(position)
        ])

        # 청산 조건: 빠른 추세 종료 대응
        exit_long_cond = all([
            current_price > latest['BB_middle'],  # 볼린저 중간선 복귀: 반등 완료
            latest['RSI'] > 50,  # RSI 중립 이상
            orderbook['mpr'] < 0.4,  # 매수 압력 급감
            latest['ATR'] > atr_ma * 2,  # 변동성 급등
            current_price - position['avg_price'] < -0.01 * position['avg_price']  # 1% 손절
        ])

        exit_short_cond = all([
            current_price < latest['BB_middle'],  # 볼린저 중간선 이탈: 하락 종료
            latest['RSI'] < 50,  # RSI 중립 이하
            orderbook['mpr'] > 0.55,  # 매도 압력 감소
            latest['ATR'] > atr_ma * 2,  # 변동성 급등
            current_price - position['avg_price'] > 0.01 * position['avg_price']  # 1% 손절 (숏 기준 반대 방향)
        ])

        # 포지션 없음: 신규 진입
        if enter_long_cond:
            if self._check_open_condition(position):
                size = self._calculate_order_size(current_price, position)
                signals.update({
                    'action': 'ENTER_LONG',
                    'price': price_high,
                    'amount': size,
                    'reason': f"RSI다이버전스_반등(RSI:{latest['RSI']:.1f}/MPR:{orderbook['mpr']:.2f})"
                })
                return signals
        elif enter_short_cond:
            if self._check_open_condition(position):
                size = self._calculate_order_size(current_price, position)
                signals.update({
                    'action': 'ENTER_SHORT',
                    'price': price_low,
                    'amount': size,
                    'reason': f"RSI다이버전스_하락(RSI:{latest['RSI']:.1f}/MPR:{orderbook['mpr']:.2f})"
                })
                return signals

        # 포지션 보유 중: 빠른 청산
        elif position_amount > 0 and exit_long_cond:
            if self._check_close_condition(position):
                size = abs(self._calculate_order_size(current_price, position))
                signals.update({
                    'action': 'EXIT_LONG',
                    'price': price_low,
                    'amount': size,
                    'reason': f"반등종료(RSI:{latest['RSI']:.1f}/MPR:{orderbook['mpr']:.2f})"
                })
                return signals
        elif position_amount < 0 and exit_short_cond:
            if self._check_close_condition(position):
                size = abs(self._calculate_order_size(current_price, position))
                signals.update({
                    'action': 'EXIT_SHORT',
                    'price': price_high,
                    'amount': size,
                    'reason': f"하락종료(RSI:{latest['RSI']:.1f}/MPR:{orderbook['mpr']:.2f})"
                })
                return signals

        return signals

    def _calculate_order_size(self, current_price, position: Dict) -> float:  # 반환형 Dict → float 수정
        """
        주문 수량 계산
        - 신규 진입 시 order_amount 계산, 청산 시 position_amount 반환
        """
        balance_data = self.data_handler.balance_data
        usdt_free = balance_data['free']  # 사용 가능한 USDT 잔고
        wallet = balance_data['wallet']   # 전체 지갑 잔고

        avg_price = position['avg_price']          # 평균 진입 가격 (0이면 포지션 없음)
        position_amount = position['position_amount']  # 현재 포지션 수량
        unrealized_profit = position['unrealizedProfit']  # 미실현 손익
        leverage = position['leverage']            # 레버리지 배율

        order_balance = round(wallet * TRADE_RATE * leverage, 2)  # 매매 실행 금액 (USDT)
        order_amount = round(order_balance / current_price, 0)    # 신규 주문 수량 (코인 수량)
        balance_amount = round(avg_price * abs(position_amount) + unrealized_profit, 2)  # 보유 코인의 현재 평가 금액

        return abs(position_amount) if avg_price != 0 and abs(position_amount) > 0 else order_amount

    def _check_open_condition(self, position: Dict) -> bool:
        """
        포지션 진입 가능 여부 확인
        - 자금 여력과 손실 상태를 기준으로 신규/추가 진입 허용 여부 판단
        """
        avg_price = position['avg_price']          # 평균 진입 가격
        position_amount = position['position_amount']  # 포지션 수량
        unrealized_profit = position['unrealizedProfit']  # 미실현 손익
        leverage = position['leverage']            # 레버리지
        balance_data = self.data_handler.balance_data
        usdt_free = balance_data['free']  # 사용 가능한 USDT 잔고
        wallet = balance_data['wallet']   # 전체 지갑 잔고
        order_balance = round(wallet * TRADE_RATE, 2)  # 매매 실행 금액 (USDT)
        balance_amount = round((avg_price * abs(position_amount) + unrealized_profit) / leverage, 2)  # 보유 코인의 평가 금액

        mygain = (unrealized_profit / (avg_price * abs(position_amount))) * 100 * leverage if avg_price != 0 and position_amount != 0 else 0  # 현재 수익률 계산

        condition1 = usdt_free > order_balance * 1.1  # 사용 가능 잔고가 주문 금액의 1.1배 이상인지 확인
        condition2 = (avg_price == 0) or (mygain < -5 and order_balance > balance_amount)  # 포지션 없거나, 손실 -5% 초과 시 추가 진입 허용

        return condition1 and condition2

    def _check_close_condition(self, position: Dict) -> bool:
        """
        포지션 청산 가능 여부 확인
        - 이익 실현(0.2%) 또는 손절(-5%) 조건 충족 시 청산 허용
        """
        avg_price = position['avg_price']          # 평균 진입 가격
        position_amount = position['position_amount']  # 포지션 수량
        unrealized_profit = position['unrealizedProfit']  # 미실현 손익
        leverage = position['leverage']            # 레버리지

        mygain = (unrealized_profit / (avg_price * abs(position_amount))) * 100 * leverage if avg_price != 0 and position_amount != 0 else 0  # 현재 수익률 계산
        condition1 = abs(position_amount) > 0 and (mygain > 0.2 or mygain < -5)  # 포지션 보유 시 이익 0.2% 이상 또는 손실 -5% 이하

        return condition1