"""
测试 CTA 策略参数传递
"""

import os
os.environ['PYTHONUNBUFFERED'] = '1'

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.app.cta_strategy import CtaStrategyApp

from vnpy.app.cta_news_trading.strategy import NewsTradingStrategy

def test_params():
    """测试参数传递"""

    print("=" * 60)
    print("CTA 策略参数传递测试")
    print("=" * 60)

    # 1. 创建引擎
    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)
    cta_engine = main_engine.add_app(CtaStrategyApp)
    cta_engine.init_engine()

    # 2. 配置 setting
    setting = {
        "execution_mode": "manual",
        "sentiment_threshold": 0.6,
        "enable_lark_push": True,
        "lark_webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/a97ae0ac-e449-44bd-9bfb-de4b6acd31ba",
        "analyzer_type": "keyword",
    }

    print(f"\n[INPUT] setting: {setting}")
    print(f"[INPUT] lark_webhook_url in setting: {'lark_webhook_url' in setting}")

    # 3. 注册策略类
    cta_engine.classes["TestStrategy"] = NewsTradingStrategy

    # 4. 添加策略
    cta_engine.add_strategy(
        class_name="TestStrategy",
        strategy_name="test_strategy",
        vt_symbol="BTCUSDT.SSE",
        setting=setting
    )

    # 5. 初始化策略（必须！）
    print("\n[INIT] 初始化策略...")
    futures = cta_engine.init_all_strategies()
    for strategy_name, future in futures.items():
        try:
            future.result(timeout=10)
            print(f"[INIT] {strategy_name} 初始化完成")
        except Exception as e:
            print(f"[INIT] {strategy_name} 初始化失败: {e}")
            import traceback
            traceback.print_exc()

    # 6. 获取策略实例
    strategy = cta_engine.strategies.get("test_strategy")

    if strategy:
        print(f"\n[CHECK] strategy.execution_mode: {strategy.execution_mode}")
        print(f"[CHECK] strategy.enable_lark_push: {strategy.enable_lark_push}")
        print(f"[CHECK] strategy.lark_webhook_url: '{strategy.lark_webhook_url}'")
        print(f"[CHECK] strategy.sentiment_threshold: {strategy.sentiment_threshold}")
        print(f"[CHECK] strategy.analyzer_type: {strategy.analyzer_type}")

        print(f"\n[PROBLEM] lark_webhook_url 是否为空: {not strategy.lark_webhook_url}")
    else:
        print("[ERROR] 策略未找到")

    # 6. 检查 cta_engine
    print(f"\n[CHECK] cta_engine: {cta_engine}")
    print(f"[CHECK] cta_engine.main_engine: {cta_engine.main_engine}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    test_params()
