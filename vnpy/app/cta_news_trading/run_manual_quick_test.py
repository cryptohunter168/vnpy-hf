"""
新闻驱动交易策略 - 仅通知模式（快速测试版）
降低阈值，缩短新闻获取间隔，便于快速测试
"""

import os
os.environ['PYTHONUNBUFFERED'] = '1'

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.app.cta_strategy import CtaStrategyApp

from .strategy import NewsTradingStrategy
from vnpy.gateway.news.news_gateway import get_news_gateway


def run_manual_mode():
    """运行仅通知模式（快速测试）"""

    print("=" * 60, flush=True)
    print("新闻驱动交易策略 - 仅通知模式（快速测试）", flush=True)
    print("=" * 60, flush=True)

    # 1. 创建事件引擎
    event_engine = EventEngine()

    # 2. 创建主引擎
    main_engine = MainEngine(event_engine)

    # 3. 配置新闻网关（降低间隔到5秒）
    print("\n1. 配置新闻网关", flush=True)
    news_config = {
        "fetch_interval": 5,  # 改为5秒获取一次
        "news_sources": [
            {
                "type": "mock",
                "name": "测试新闻",
                "url": "http://finance.sina.com.cn/roll/finance.d.html"
            }
        ]
    }

    # 创建新闻网关实例
    news_gateway = get_news_gateway(event_engine, news_config)
    print(f"新闻网关已创建，新闻源数量: {len(news_gateway.news_sources)}", flush=True)

    # 4. 添加CTA策略应用
    print("2. 添加CTA策略应用", flush=True)
    cta_engine = main_engine.add_app(CtaStrategyApp)

    # 5. 注册策略类
    cta_engine.classes["NewsTradingStrategy"] = NewsTradingStrategy

    # 6. 初始化CTA引擎
    print("3. 初始化CTA引擎", flush=True)
    cta_engine.init_engine()

    # 7. 添加策略（降低阈值）
    print("4. 添加新闻驱动交易策略", flush=True)
    setting = {
        "execution_mode": "manual",
        "sentiment_threshold": 0.1,  # 降低到0.1，更容易触发
        "confidence_threshold": 0.1,  # 降低到0.1，更容易触发
        "trade_volume": 0.01,
        "max_single_order": 50000.0,
        "max_daily_orders": 10,
        "news_valid_time": 300,
        "enable_lark_push": True,

        # 飞书配置（使用 Webhook）
        "lark_webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/a97ae0ac-e449-44bd-9bfb-de4b6acd31ba",

        "lark_approval_timeout": 300,

        "analyzer_type": "keyword",  # 使用关键词分析器，更可靠
    }

    cta_engine.add_strategy(
        class_name="NewsTradingStrategy",
        strategy_name="news_strategy_manual",
        vt_symbol="BTCUSDT.SSE",
        setting=setting
    )
    print("\n注意：仅通知模式，不会自动执行交易", flush=True)

    # 8. 初始化所有策略
    print("\n5. 初始化策略", flush=True)
    futures = cta_engine.init_all_strategies()

    # 等待所有策略初始化完成
    import time
    for strategy_name, future in futures.items():
        try:
            future.result(timeout=10)
            print(f"   {strategy_name} 初始化完成")
        except Exception as e:
            print(f"   {strategy_name} 初始化失败: {e}")

    # 验证策略是否正确加载和初始化
    print("\n验证策略状态:")
    strategy = cta_engine.strategies.get("news_strategy_manual")
    if strategy:
        print(f"   [OK] 策略实例已创建")
        print(f"   [OK] 策略类名: {strategy.__class__.__name__}")
        print(f"   [OK] 策略已初始化: {strategy.inited}")
        print(f"   [OK] 交易品种: {strategy.vt_symbol}")
        print(f"   [OK] 执行模式: {strategy.execution_mode}")
        print(f"   [OK] 情感阈值: {strategy.sentiment_threshold}")
        print(f"   [OK] 置信度阈值: {strategy.confidence_threshold}")
        print(f"   [OK] 分析器类型: {strategy.analyzer_type}")
        print(f"   [OK] 飞书推送启用: {strategy.enable_lark_push}")
        print(f"   [OK] Webhook URL: {strategy.lark_webhook_url}")

        # 检查 execution_engine
        if hasattr(strategy, 'execution_engine') and strategy.execution_engine:
            print(f"   [OK] 执行引擎已创建")
            if hasattr(strategy.execution_engine, 'lark_client'):
                lark_client = strategy.execution_engine.lark_client
                if lark_client:
                    print(f"   [OK] 飞书客户端已初始化: {type(lark_client).__name__}")
                else:
                    print(f"   [ERROR] 飞书客户端未初始化")
            else:
                print(f"   [ERROR] 执行引擎没有 lark_client 属性")
        else:
            print(f"   [ERROR] 执行引擎未创建")
    else:
        print(f"   [ERROR] 策略未找到")
        print(f"   [DEBUG] cta_engine.strategies keys: {list(cta_engine.strategies.keys())}")

    # 9. 启动所有策略
    print("\n6. 启动策略", flush=True)
    cta_engine.start_all_strategies()

    # 10. 连接新闻网关（开始采集新闻）
    print("\n7. 启动新闻网关", flush=True)
    news_gateway.connect()
    print("   新闻网关已启动（每5秒获取一次新闻）", flush=True)

    print("\n" + "=" * 60)
    print("系统已启动 - 仅通知模式（快速测试）")
    print("新闻分析结果将推送到飞书，不自动执行交易")
    print("每5秒会发送一条测试新闻到飞书")
    print("按 Ctrl+C 停止")
    print("=" * 60, flush=True)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止系统...", flush=True)
        news_gateway.close()
        cta_engine.stop_all_strategies()
        event_engine.stop()
        print("系统已停止", flush=True)


if __name__ == "__main__":
    run_manual_mode()
