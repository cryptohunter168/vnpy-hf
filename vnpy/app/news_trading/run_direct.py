"""
新闻驱动交易策略 - 模式一：直接执行
分析新闻后直接执行交易指令
"""

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.gateway.binance import BinanceGateway
from vnpy.app.cta_strategy import CtaStrategyApp

from .strategy import NewsTradingStrategy
from .news_gateway import NEWS_CONFIG_EXAMPLE


def run_direct_mode():
    """运行直接执行模式"""

    print("=" * 60)
    print("新闻驱动交易策略 - 直接执行模式")
    print("=" * 60)

    # 1. 创建事件引擎
    event_engine = EventEngine()
    event_engine.start()

    # 2. 创建主引擎
    main_engine = MainEngine(event_engine)

    # 3. 添加交易网关（示例：Binance）
    print("\n1. 添加Binance交易网关")
    main_engine.add_gateway(BinanceGateway)

    # 4. 添加CTA策略应用
    print("2. 添加CTA策略应用")
    cta_engine = CtaStrategyApp(main_engine, event_engine)

    # 5. 配置新闻网关（使用Mock源进行演示）
    print("3. 配置新闻网关")
    news_config = {
        "fetch_interval": 30,  # 每30秒获取一次新闻
        "news_sources": [
            {
                "type": "mock",  # 使用模拟新闻源
                "name": "Mock"
            }
        ]
    }

    # 如果使用真实新闻源，配置如下：
    # news_config = {
    #     "fetch_interval": 60,
    #     "news_sources": [
    #         {
    #             "type": "rss",
    #             "name": "新浪财经",
    #             "url": "http://finance.sina.com.cn/roll/finance.d.html"
    #         }
    #     ]
    # }

    # 6. 初始化CTA引擎
    print("4. 初始化CTA引擎")
    cta_engine.init_engine()

    # 7. 添加策略
    print("5. 添加新闻驱动交易策略")
    setting = {
        "vt_symbol": "BTCUSDT.BINANCE",
        "execution_mode": "direct",  # 直接执行模式
        "sentiment_threshold": 0.6,  # 情感阈值
        "confidence_threshold": 0.7,  # 置信度阈值
        "trade_volume": 0.01,  # 交易数量（BTC）
        "max_single_order": 1000.0,  # 单笔最大金额
        "max_daily_orders": 10,  # 每日最大交易次数
        "news_valid_time": 300,  # 新闻有效时间（秒）
        "enable_lark_push": False,  # 不推送飞书
        "analyzer_type": "snownlp",  # 使用SnowNLP分析器
    }

    cta_engine.add_strategy(NewsTradingStrategy, "news_strategy_direct", setting)

    # 8. 连接交易网关
    print("\n6. 连接交易网关")
    # 注意：实际交易需要配置API密钥
    # gateway_setting = {
    #     "key": "your_binance_api_key",
    #     "secret": "your_binance_api_secret",
    #     "session_number": 3,
    #     "proxy_host": "",
    #     "proxy_port": 0,
    # }
    # main_engine.connect(gateway_setting, "BINANCE")

    print("注意：当前使用模拟模式，不进行实际交易")
    print("要进行实际交易，请配置API密钥并取消注释上面的连接代码")

    # 9. 启动所有策略
    print("\n7. 启动策略")
    cta_engine.start_all()

    print("\n" + "=" * 60)
    print("系统已启动，按 Ctrl+C 停止")
    print("=" * 60)

    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止系统...")
        cta_engine.stop_all()
        event_engine.stop()
        print("系统已停止")


if __name__ == "__main__":
    run_direct_mode()
