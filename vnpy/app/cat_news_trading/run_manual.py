"""
新闻驱动交易策略 - 模式四：仅通知模式
只推送分析结果，不自动执行交易
"""

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.app.cta_strategy import CtaStrategyApp

from .strategy import NewsTradingStrategy
from vnpy.gateway.news.news_gateway import get_news_gateway


def run_manual_mode():
    """运行仅通知模式"""

    print("=" * 60)
    print("新闻驱动交易策略 - 仅通知模式")
    print("=" * 60)

    # 1. 创建事件引擎
    event_engine = EventEngine()

    # 2. 创建主引擎
    main_engine = MainEngine(event_engine)

    # 3. 配置新闻网关
    print("\n1. 配置新闻网关")
    news_config = {
        "fetch_interval": 60,
        "news_sources": [
            {
                "type": "mock",
                "name": "新浪财经",
                "url": "http://finance.sina.com.cn/roll/finance.d.html"
            }
        ]
    }

    # 创建新闻网关实例
    news_gateway = get_news_gateway(event_engine, news_config)
    print(f"   新闻网关已创建，新闻源数量: {len(news_gateway.news_sources)}")

    # 4. 添加CTA策略应用
    print("2. 添加CTA策略应用")
    cta_engine = main_engine.add_app(CtaStrategyApp)

    # 5. 注册策略类
    cta_engine.classes["NewsTradingStrategy"] = NewsTradingStrategy

    # 6. 初始化CTA引擎
    print("3. 初始化CTA引擎")
    cta_engine.init_engine()

    # 7. 添加策略
    print("4. 添加新闻驱动交易策略")
    setting = {
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

    cta_engine.add_strategy(
        class_name="NewsTradingStrategy",
        strategy_name="news_strategy_manual",
        vt_symbol="BTCUSDT.BINANCE",
        setting=setting
    )

    print("\n注意：仅通知模式，不会自动执行交易")
    print("如需执行交易，请通过飞书命令或手动下单")

    # 7. 启动所有策略
    print("\n5. 启动策略")
    cta_engine.start_all_strategies()

    # 8. 连接新闻网关（开始采集新闻）
    print("\n6. 启动新闻网关")
    news_gateway.connect()
    print("   新闻网关已启动")

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
        news_gateway.close()
        cta_engine.stop_all_strategies()
        event_engine.stop()
        print("系统已停止")


if __name__ == "__main__":
    run_manual_mode()
