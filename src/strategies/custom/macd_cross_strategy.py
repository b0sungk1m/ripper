"""
Ripper's MACD Crossover Strategy
Evaluates MACD crossovers on 1s, 1m, and 15m timeframes.
"""

from ..base_strategy import BaseStrategy
from src.config import MONITORED_TOKENS
import pandas as pd
from termcolor import cprint
from src import nice_funcs as n

class MACDStrategy(BaseStrategy):
    def __init__(self):
        """Initialize the MACD strategy with default MACD parameters."""
        super().__init__("MACD Crossover")
        self.fast = 12
        self.slow = 26
        self.signal_period = 9

    def calculate_macd(self, data: pd.DataFrame):
        """Calculate MACD and Signal line from close prices."""
        ema_fast = data['close'].ewm(span=self.fast, adjust=False).mean()
        ema_slow = data['close'].ewm(span=self.slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.signal_period, adjust=False).mean()
        return macd_line, signal_line

    def generate_signals(self) -> dict:
        """
        Generate trading signals by checking for MACD crossovers across
        1s, 1m, and 5m timeframes. Uses majority rule: if at least two
        timeframes show a bullish (or bearish) crossover, signal BUY (or SELL).
        """
        try:
            for token in MONITORED_TOKENS:
                timeframe_signals = {}
                metadata = {}

                for tf in ['1']:
                    data = n.get_data(token, days_back_4_data=3, timeframe=tf)
                    if data is None or data.empty or len(data) < 2:
                        continue

                    macd_line, signal_line = self.calculate_macd(data)
                    prev_macd = macd_line.iloc[-2]
                    prev_signal = signal_line.iloc[-2]
                    curr_macd = macd_line.iloc[-1]
                    curr_signal = signal_line.iloc[-1]

                    if prev_macd < prev_signal and curr_macd > curr_signal:
                        timeframe_signals[tf] = 'BULLISH'
                    elif prev_macd > prev_signal and curr_macd < curr_signal:
                        timeframe_signals[tf] = 'BEARISH'
                    else:
                        timeframe_signals[tf] = 'NEUTRAL'

                    metadata[tf] = {
                        'prev_macd': float(prev_macd),
                        'prev_signal': float(prev_signal),
                        'current_macd': float(curr_macd),
                        'current_signal': float(curr_signal)
                    }

                # Print timeframe signals
                cprint(f"📊 Timeframe Signals for {token}:", "white", "on_blue")
                for tf, signal in timeframe_signals.items():
                    cprint(f"  • {tf}: {signal}", "white", "on_blue")
                
                # Majority rule decision
                bullish = sum(1 for s in timeframe_signals.values() if s == 'BULLISH')
                bearish = sum(1 for s in timeframe_signals.values() if s == 'BEARISH')
                direction = 'NEUTRAL'
                signal_val = 0

                if bullish >= 2:
                    direction = 'BUY'
                    signal_val = 1.0
                elif bearish >= 2:
                    direction = 'SELL'
                    signal_val = 1.0

                # Get a current price from 1s data if available, else 1m fallback
                price_data = n.get_data(token, days_back_4_data=3, timeframe='1s')
                if price_data is None or price_data.empty:
                    price_data = n.get_data(token, days_back_4_data=3, timeframe='1m')
                current_price = float(price_data['close'].iloc[-1]) if price_data is not None and not price_data.empty else 0.0

                signal = {
                    'token': token,
                    'signal': signal_val,
                    'direction': direction,
                    'metadata': {
                        'strategy_type': 'macd_crossover',
                        'timeframe_signals': timeframe_signals,
                        'details': metadata,
                        'current_price': current_price
                    }
                }

                if self.validate_signal(signal):
                    signal['metadata'] = self.format_metadata(signal['metadata'])
                    return signal

            return None

        except Exception as e:
            cprint(f"❌ Error generating MACD signals: {str(e)}", "red")
            return None