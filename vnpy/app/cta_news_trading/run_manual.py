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
from .config_manager import get_config
from vnpy.gateway.news.news_gateway import get_news_gateway


def run_manual_mode():
    """运行仅通知模式"""

    print("=" * 60, flush=True)
    print("新闻驱动交易策略 - 仅通知模式", flush=True)
    print("=" * 60, flush=True)

    # 加载统一配置
    print("[INFO] 加载配置文件...", flush=True)
    config = get_config()

    # 1. 创建事件引擎
    print("[DEBUG] 开始创建事件引擎...", flush=True)
    event_engine = EventEngine()
    print("[DEBUG] 事件引擎创建完成", flush=True)

    # 2. 创建主引擎
    print("[DEBUG] 开始创建主引擎...", flush=True)
    main_engine = MainEngine(event_engine)
    print("[DEBUG] 主引擎创建完成", flush=True)

    # 3. 配置新闻网关（从配置文件读取）
    print("\n1. 配置新闻网关", flush=True)
    print("[DEBUG] 开始配置新闻网关...", flush=True)
    news_config = config.get_news_config()

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

    # 7. 添加策略（从配置文件读取）
    print("4. 添加新闻驱动交易策略", flush=True)
    print("[DEBUG] 从配置文件读取策略配置...", flush=True)

    strategy_config = config.get_strategy_config()
    class_name = strategy_config["class_name"]
    strategy_name = strategy_config["strategy_name"]
    vt_symbol = strategy_config["vt_symbol"]
    setting = strategy_config["setting"]

    print(f"[INFO] 策略名称: {strategy_name}", flush=True)
    print(f"[INFO] 交易品种: {vt_symbol}", flush=True)
    print(f"[INFO] 执行模式: {setting.get('execution_mode')}", flush=True)
    print(f"[INFO] 飞书 Webhook: {setting.get('lark_webhook_url', '')[:50]}...", flush=True)

    cta_engine.add_strategy(
        class_name=class_name,
        strategy_name=strategy_name,
        vt_symbol=vt_symbol,
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
