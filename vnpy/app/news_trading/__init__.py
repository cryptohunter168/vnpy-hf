"""
新闻驱动交易应用
"""

from .config import ExecutionConfig, ExecutionMode, Priority
from .strategy import NewsTradingStrategy, MultiSymbolNewsStrategy
from .news_gateway import NewsGateway, NEWS_CONFIG_EXAMPLE
from .sentiment_analyzer import SentimentAnalyzer, SnowNLPSentimentAnalyzer, BERTSentimentAnalyzer, NewsAnalyzer, get_analyzer
from .lark_client import LarkClient, LarkWebhookClient, verify_webhook_signature
from .lark_command_listener import LarkCommandListener, TradeCommandParser, create_trade_command_handlers
from .execution_engine import ExecutionEngine, TradeCommand

__all__ = [
    # Config
    "ExecutionConfig",
    "ExecutionMode",
    "Priority",

    # Strategy
    "NewsTradingStrategy",
    "MultiSymbolNewsStrategy",

    # News Gateway
    "NewsGateway",
    "NEWS_CONFIG_EXAMPLE",

    # Sentiment Analyzer
    "SentimentAnalyzer",
    "SnowNLPSentimentAnalyzer",
    "BERTSentimentAnalyzer",
    "NewsAnalyzer",
    "get_analyzer",

    # Lark Client
    "LarkClient",
    "LarkWebhookClient",
    "verify_webhook_signature",

    # Lark Command Listener
    "LarkCommandListener",
    "TradeCommandParser",
    "create_trade_command_handlers",

    # Execution Engine
    "ExecutionEngine",
    "TradeCommand",
]
