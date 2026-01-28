"""
新闻驱动交易策略 - 模式四：仅通知模式
只推送分析结果，不自动执行交易
"""

import os

# 强制刷新输出
os.environ['PYTHONUNBUFFERED'] = '1'

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.app.cta_strategy import CtaStrategyApp

from .strategy import NewsTradingStrategy
from vnpy.gateway.news.news_gateway import get_news_gateway


def run_manual_mode():
    """运行仅通知模式"""

    print("=" * 60, flush=True)
    print("新闻驱动交易策略 - 仅通知模式", flush=True)
    print("=" * 60, flush=True)
    print("[DEBUG] 开始创建事件引擎...", flush=True)

    # 1. 创建事件引擎
    event_engine = EventEngine()
    print("[DEBUG] 事件引擎创建完成", flush=True)

    # 2. 创建主引擎
    print("[DEBUG] 开始创建主引擎...", flush=True)
    main_engine = MainEngine(event_engine)
    print("[DEBUG] 主引擎创建完成", flush=True)

    # 3. 配置新闻网关
    print("\n1. 配置新闻网关", flush=True)
    print("[DEBUG] 开始配置新闻网关...", flush=True)
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
    print(f"[DEBUG] 新闻网关已创建，新闻源数量: {len(news_gateway.news_sources)}", flush=True)
    print("[DEBUG] 新闻网关创建完成", flush=True)

    # 4. 添加CTA策略应用
    print("2. 添加CTA策略应用", flush=True)
    print("[DEBUG] 开始添加CTA策略应用...", flush=True)
    cta_engine = main_engine.add_app(CtaStrategyApp)
    print(f"[DEBUG] CTA引擎创建完成: {type(cta_engine)}", flush=True)

    # 5. 注册策略类
    print("[DEBUG] 注册策略类...", flush=True)
    cta_engine.classes["NewsTradingStrategy"] = NewsTradingStrategy
    print(f"[DEBUG] 策略类已注册，当前classes: {list(cta_engine.classes.keys())}", flush=True)

    # 6. 初始化CTA引擎
    print("3. 初始化CTA引擎", flush=True)
    print("[DEBUG] 开始初始化CTA引擎...", flush=True)
    cta_engine.init_engine()
    print("[DEBUG] CTA引擎初始化完成", flush=True)

    # 7. 添加策略
    print("4. 添加新闻驱动交易策略", flush=True)
    print("[DEBUG] 准备策略配置...", flush=True)
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

    print(f"[DEBUG] 调用 add_strategy...", flush=True)
    cta_engine.add_strategy(
        class_name="NewsTradingStrategy",
        strategy_name="news_strategy_manual",
        vt_symbol="BTCUSDT.SSE",  # 使用 SSE 交易所（vn.py 支持的交易所）
        setting=setting
    )
    print(f"[DEBUG] 策略添加完成，strategies keys: {list(cta_engine.strategies.keys())}", flush=True)
    print("\n注意：仅通知模式，不会自动执行交易", flush=True)
    print("如需执行交易，请通过飞书命令或手动下单")

    # 7. 初始化所有策略（必须在启动之前）
    print("\n5. 初始化策略")
    futures = cta_engine.init_all_strategies()

    # 等待所有策略初始化完成
    import time
    for strategy_name, future in futures.items():
        try:
            future.result(timeout=10)  # 等待最多10秒
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
    else:
        print(f"   [ERROR] 策略未找到")
        print(f"   [DEBUG] cta_engine.strategies keys: {list(cta_engine.strategies.keys())}")

    # 8. 启动所有策略
    print("\n6. 启动策略")
    cta_engine.start_all_strategies()

    # 9. 连接新闻网关（开始采集新闻）
    print("\n7. 启动新闻网关")
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
