"""
🌙 Moon Dev's Custom Strategies Package
"""
from src.strategies.base_strategy import BaseStrategy
from .example_strategy import ExampleStrategy
from .macd_cross_strategy import MACDStrategy

__all__ = ['ExampleStrategy', 'MyStrategy', 'MACDStrategy'] 