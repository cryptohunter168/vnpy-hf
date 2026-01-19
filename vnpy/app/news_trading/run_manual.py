"""
新闻驱动交易策略 - 模式四：仅通知模式
只推送分析结果，不自动执行交易
"""

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.gateway.binance import BinanceGateway
from vnpy.app.cta_strategy import CtaStrategyApp

from .strategy import NewsTradingStrategy
from .news_gateway import NEWS_CONFIG_EXAMPLE


def run_manual_mode():
    """运行仅通知模式"""

    print("=" * 60)
    print("新闻驱动交易策略 - 仅通知模式")
    print("=" * 60)

    # 1. 创建事件引擎
    event_engine = EventEngine()
    event_engine.start()

    # 2. 创建主引擎
    main_engine = MainEngine(event_engine)

    # 3. 添加交易网关
    print("\n1. 添加Binance交易网关")
    main_engine.add_gateway(BinanceGateway)

    # 4. 添加CTA策略应用
    print("2. 添加CTA策略应用")
    cta_engine = CtaStrategyApp(main_engine, event_engine)

    # 5. 配置新闻网关
    print("3. 配置新闻网关")
    news_config = {
        "fetch_interval": 60,
        "news_sources": [
            {
                "type": "rss",
                "name": "新浪财经",
                "url": "http://finance.sina.com.cn/roll/finance.d.html"
            }
        ]
    }

    # 6. 初始化CTA引擎
    print("4. 初始化CTA引擎")
    cta_engine.init_engine()

    # 7. 添加策略
    print("5. 添加新闻驱动交易策略")
    setting = {
        "vt_symbol": "BTCUSDT.BINANCE",
        "execution_mode": "manual",  # 仅通知模式
        "sentiment_threshold": 0.6,
        "confidence_threshold": 0.7,
        "trade_volume": 0.01,
        "max_single_order": 50000.0,
        "max_daily_orders": 10,
        "news_valid_time": 300,
        "enable_lark_push": True,

        # 飞书配置
        "lark_app_id": "your_lark_app_id",
        "lark_app_secret": "your_lark_app_secret",
        "lark_chat_id": "oc_xxxxxxxxxxxxxxxx",
        "lark_approval_timeout": 300,

        "analyzer_type": "snownlp",
    }

    cta_engine.add_strategy(NewsTradingStrategy, "news_strategy_manual", setting)

    # 8. 连接交易网关
    print("\n6. 连接交易网关")
    # gateway_setting = {
    #     "key": "your_binance_api_key",
    #     "secret": "your_binance_api_secret",
    #     "session_number": 3,
    #     "proxy_host": "",
    #     "proxy_port": 0,
    # }
    # main_engine.connect(gateway_setting, "BINANCE")

    print("注意：仅通知模式，不会自动执行交易")
    print("如需执行交易，请通过飞书命令或手动下单")

    # 9. 启动所有策略
    print("\n7. 启动策略")
    cta_engine.start_all()

    print("\n" + "=" * 60)
    print("系统已启动 - 仅通知模式")
    print("新闻分析结果将推送到飞书，不自动执行交易")
    print("按 Ctrl+C 停止")
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
    run_manual_mode()
