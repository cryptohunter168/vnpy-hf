"""
Event type string used in VN Trader.
"""

from vnpy.event import EVENT_TIMER  # noqa

EVENT_TICK = "eTick."
EVENT_TRADE = "eTrade."
EVENT_ORDER = "eOrder."
EVENT_POSITION = "ePosition."
EVENT_ACCOUNT = "eAccount."
EVENT_CONTRACT = "eContract."
EVENT_LOG = "eLog"

# 扩展
EVENT_BAR = "eBar."
EVENT_STRATEGY_POS = "eStrategyPos."
EVENT_STRATEGY_SNAPSHOT = "eStrategySnapshot."

# 拓展， 支持股票账号中，历史交成交/历史委托/资金流水
EVENT_HISTORY_TRADE = 'eHistoryTrade.'
EVENT_HISTORY_ORDER = 'eHistoryOrder.'
EVENT_FUNDS_FLOW = 'eFundsFlow.'


# 扩展，支持系统发出得异常事件
EVENT_ERROR = 'eError'
EVENT_WARNING = 'eWarning'
EVENT_CRITICAL = 'eCritical'

# 新闻事件
EVENT_NEWS = 'eNews.'                # 新闻数据事件
EVENT_NEWS_ANALYSIS = 'eNewsAnalysis'  # 新闻分析结果事件
EVENT_TRADE_COMMAND = 'eTradeCommand' # 交易指令事件
