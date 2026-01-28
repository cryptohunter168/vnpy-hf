"""
新闻驱动交易策略 - 完整版本（使用 NewsGateway）
演示完整的调用流程
"""

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.gateway.binance import BinanceGateway
from vnpy.app.cta_strategy import CtaStrategyApp

from .strategy import NewsTradingStrategy
from .news_gateway import get_news_gateway


def run_with_news_gateway():
    """运行完整的新闻网关集成版本"""

    print("=" * 60)
    print("新闻驱动交易策略 - 完整版本（使用 NewsGateway）")
    print("=" * 60)

    # ==================== 第一步：创建事件引擎 ====================
    print("\n[1] 创建事件引擎")
    event_engine = EventEngine()
    event_engine.start()
    print("    ✅ 事件引擎已启动")

    # ==================== 第二步：创建主引擎 ====================
    print("\n[2] 创建主引擎")
    main_engine = MainEngine(event_engine)
    print("    ✅ 主引擎已创建")

    # ==================== 第三步：添加交易网关 ====================
    print("\n[3] 添加交易网关")
    main_engine.add_gateway(BinanceGateway)
    print("    ✅ Binance网关已添加")

    # ==================== 第四步：添加CTA策略应用 ====================
    print("\n[4] 添加CTA策略应用")
    cta_engine = CtaStrategyApp(main_engine, event_engine)
    cta_engine.init_engine()
    print("    ✅ CTA引擎已初始化")

    # ==================== 第五步：创建新闻网关 ====================
    print("\n[5] 创建新闻网关")
    news_config = {
        "fetch_interval": 60,  # 每60秒获取一次新闻
        "news_sources": [
            {
                "type": "mock",  # 使用模拟新闻源进行演示
                "name": "Mock"
            }
            # 如果使用真实新闻源，配置如下：
            # {
            #     "type": "rss",
            #     "name": "新浪财经",
            #     "url": "http://finance.sina.com.cn/roll/finance.d.html"
            # },
            # {
            #     "type": "api",
            #     "name": "NewsAPI",
            #     "url": "https://newsapi.org/v2/top-headlines",
            #     "api_key": "your_api_key",
            #     "params": {
            #         "country": "cn",
            #         "category": "business"
            #     }
            # }
        ]
    }

    # 创建新闻网关实例
    news_gateway = get_news_gateway(event_engine, news_config)
    print("    ✅ 新闻网关已创建")
    print(f"    📰 新闻源数量: {len(news_gateway.news_sources)}")
    for source in news_gateway.news_sources:
        print(f"       - {source.name} ({type(source).__name__})")

    # ==================== 第六步：设置新闻网关回调 ====================
    print("\n[6] 设置新闻网关回调")

    def news_callback(news_list):
        """新闻回调函数"""
        print(f"\n📰 收到 {len(news_list)} 条新闻:")
        for news in news_list:
            print(f"   [{news.get('source', '')}] {news.get('title', '')}")

    news_gateway.set_callback(news_callback)
    print("    ✅ 新闻回调已设置")

    # ==================== 第七步：启动新闻网关 ====================
    print("\n[7] 启动新闻网关")
    news_gateway.connect()
    print("    ✅ 新闻网关已启动（开始定时采集新闻）")

    # ==================== 第八步：添加策略 ====================
    print("\n[8] 添加新闻驱动交易策略")
    setting = {
        "vt_symbol": "BTCUSDT.BINANCE",
        "execution_mode": "direct",  # 直接执行模式
        "sentiment_threshold": 0.6,
        "confidence_threshold": 0.7,
        "trade_volume": 0.01,
        "max_single_order": 1000.0,
        "max_daily_orders": 10,
        "news_valid_time": 300,
        "enable_lark_push": False,  # 不推送飞书
        "analyzer_type": "snownlp",
    }

    cta_engine.add_strategy(NewsTradingStrategy, "news_strategy", setting)
    print("    ✅ 策略已添加")

    # ==================== 第九步：连接交易网关（可选） ====================
    print("\n[9] 连接交易网关")
    print("    ⚠️  当前使用模拟模式，不进行实际交易")
    print("    💡 要进行实际交易，请配置API密钥并取消注释下面的代码：")
    # gateway_setting = {
    #     "key": "your_binance_api_key",
    #     "secret": "your_binance_api_secret",
    #     "session_number": 3,
    #     "proxy_host": "",
    #     "proxy_port": 0,
    # }
    # main_engine.connect(gateway_setting, "BINANCE")

    # ==================== 第十步：启动所有策略 ====================
    print("\n[10] 启动所有策略")
    cta_engine.start_all()
    print("    ✅ 策略已启动")

    # ==================== 系统运行 ====================
    print("\n" + "=" * 60)
    print("系统已启动，正在运行...")
    print("=" * 60)
    print("\n数据流程:")
    print("  NewsGateway (定时采集)")
    print("         ↓")
    print("  Event(EVENT_NEWS)")
    print("         ↓")
    print("  Strategy.on_news_event()")
    print("         ↓")
    print("  NewsAnalyzer (情感分析)")
    print("         ↓")
    print("  News_Engine (执行交易)")
    print("=" * 60)
    print("\n按 Ctrl+C 停止系统")
    print("=" * 60)

    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n正在停止系统...")
        print("\n[1] 停止所有策略")
        cta_engine.stop_all()
        print("    ✅ 策略已停止")

        print("\n[2] 关闭新闻网关")
        news_gateway.close()
        print("    ✅ 新闻网关已关闭")

        print("\n[3] 停止事件引擎")
        event_engine.stop()
        print("    ✅ 事件引擎已停止")

        print("\n" + "=" * 60)
        print("系统已完全停止")
        print("=" * 60)


if __name__ == "__main__":
    run_with_news_gateway()
